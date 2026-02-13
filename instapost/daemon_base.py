"""Base class for resilient daemons that never die on errors.

This module provides a ResilientDaemon base class that ensures daemons:
- Never exit on transient errors (network, file system, etc.)
- Automatically recover with exponential backoff
- Handle graceful shutdown on SIGTERM/SIGINT
- Provide health monitoring via heartbeat files
- Log all errors with full stack traces
"""

import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from instapost.utils import PROJECT_ROOT


class ResilientDaemon:
    """
    Base class for daemons that NEVER exit on errors.

    Design principles:
    1. NEVER exit except on explicit shutdown (SIGTERM/SIGINT/KeyboardInterrupt)
    2. All errors are logged and recovered from automatically
    3. Exponential backoff prevents tight error loops
    4. Health monitoring via heartbeat files
    5. Graceful shutdown with cleanup

    Usage:
        class MyDaemon(ResilientDaemon):
            def setup(self):
                # One-time setup
                pass

            def work(self):
                # Do work each iteration
                pass

            def cleanup(self):
                # Cleanup before shutdown
                pass

        daemon = MyDaemon(name="my-daemon", logger=my_logger)
        daemon.run()  # Runs forever until shutdown signal
    """

    def __init__(
        self,
        name: str,
        logger: logging.Logger,
        check_interval: float = 60.0,
        max_backoff: int = 300,
        heartbeat_enabled: bool = True
    ):
        """
        Initialize resilient daemon.

        Args:
            name: Daemon name (used in logs and heartbeat file)
            logger: Logger instance for this daemon
            check_interval: Seconds between work iterations (default: 60)
            max_backoff: Maximum backoff time in seconds (default: 300 = 5min)
            heartbeat_enabled: Enable heartbeat file writing (default: True)
        """
        self.name = name
        self.logger = logger
        self.check_interval = check_interval
        self.max_backoff = max_backoff
        self.heartbeat_enabled = heartbeat_enabled
        self.shutdown_requested = False
        self.consecutive_errors = 0

        # Heartbeat file path
        self.heartbeat_file = PROJECT_ROOT / f".{name}.heartbeat"

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        self.logger.info(f"🛑 {self.name} received {signal_name} - initiating graceful shutdown")
        self.shutdown_requested = True

    def _write_heartbeat(self):
        """Write heartbeat file with current timestamp."""
        if not self.heartbeat_enabled:
            return

        try:
            self.heartbeat_file.write_text(str(time.time()))
        except Exception as e:
            # Don't let heartbeat errors crash the daemon
            self.logger.debug(f"Failed to write heartbeat: {e}")

    def get_heartbeat_age(self) -> Optional[float]:
        """
        Get age of last heartbeat in seconds.

        Returns:
            Seconds since last heartbeat, or None if no heartbeat file exists
        """
        if not self.heartbeat_file.exists():
            return None

        try:
            last_heartbeat = float(self.heartbeat_file.read_text().strip())
            return time.time() - last_heartbeat
        except Exception:
            return None

    def setup(self):
        """
        Override: One-time setup before main loop starts.

        This runs once at daemon startup. If it raises an exception,
        the daemon will exit with error code 1.

        Use for:
        - Creating required directories
        - Initializing resources
        - Validating configuration
        """
        pass

    def work(self):
        """
        Override: The actual work to do each iteration.

        This is called repeatedly in the main loop. If it raises an exception,
        the error will be logged and the daemon will retry with exponential backoff.

        IMPORTANT: This should do one iteration of work, then return.
        The daemon base class handles the infinite loop and sleep intervals.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement work()")

    def cleanup(self):
        """
        Override: Cleanup before shutdown.

        This runs once when shutdown is requested (SIGTERM/SIGINT/KeyboardInterrupt).
        Use for:
        - Stopping background threads
        - Closing file handles
        - Saving state

        Exceptions in cleanup are logged but don't prevent shutdown.
        """
        pass

    def run(self):
        """
        Main daemon loop - NEVER EXITS except on explicit shutdown.

        Flow:
        1. Run setup() - if it fails, exit with error code 1
        2. Enter infinite loop:
           - Write heartbeat
           - Call work()
           - On success: reset error counter, sleep
           - On error: log, backoff, retry (NEVER exit)
        3. On shutdown signal: cleanup() and exit gracefully

        Returns:
            0 on successful shutdown, 1 on setup failure
        """
        self.logger.info(f"🚀 {self.name} starting - will run forever until shutdown signal")

        # Run one-time setup
        try:
            self.logger.debug(f"Running setup for {self.name}...")
            self.setup()
            self.logger.debug(f"Setup complete for {self.name}")
        except Exception as e:
            self.logger.critical(
                f"❌ {self.name} setup failed - cannot start: {e}",
                exc_info=True
            )
            return 1

        # OUTER LOOP - NEVER EXITS (except on shutdown signal)
        while not self.shutdown_requested:
            try:
                # Write heartbeat to show we're alive
                self._write_heartbeat()

                # Do the actual work
                self.work()

                # Success - reset error counter
                if self.consecutive_errors > 0:
                    self.logger.info(
                        f"✅ {self.name} recovered after {self.consecutive_errors} consecutive errors"
                    )
                    self.consecutive_errors = 0

                # Sleep until next iteration (unless shutdown requested)
                if not self.shutdown_requested and self.check_interval > 0:
                    self.logger.debug(f"Sleeping for {self.check_interval}s")
                    time.sleep(self.check_interval)

            except KeyboardInterrupt:
                self.logger.info(f"🛑 {self.name} received KeyboardInterrupt (Ctrl+C)")
                break  # Exit to cleanup

            except Exception as e:
                # CRITICAL: Don't exit - log and retry with exponential backoff
                self.consecutive_errors += 1

                # Calculate exponential backoff: 5s, 10s, 20s, 40s, 80s, ... up to max_backoff
                backoff = min(
                    5 * (2 ** (self.consecutive_errors - 1)),
                    self.max_backoff
                )

                self.logger.error(
                    f"❌ {self.name} error #{self.consecutive_errors}: {e}",
                    exc_info=True
                )
                self.logger.warning(
                    f"⏳ Waiting {backoff}s before retry... "
                    f"(daemon will NOT exit, will retry forever)"
                )

                # Sleep with backoff (unless shutdown requested)
                if not self.shutdown_requested:
                    time.sleep(backoff)

                # CONTINUE - daemon never exits on errors

        # Graceful shutdown
        self.logger.info(f"🛑 {self.name} shutting down gracefully...")
        try:
            self.cleanup()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}", exc_info=True)

        # Remove heartbeat file on shutdown
        try:
            if self.heartbeat_file.exists():
                self.heartbeat_file.unlink()
        except Exception:
            pass

        self.logger.info(f"✅ {self.name} stopped")
        return 0
