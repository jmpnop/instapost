# Facebook Token Expiration Explanation

## Why Some Tokens Show Dates from 1970

When running the `token-info` command, you might notice that some tokens display dates around January 1, 1970 (e.g., "1969-12-31 19:00:00") for their expiration date. This document explains why this happens.

## Understanding Facebook Token Expiration

Facebook's Graph API provides token information through the `debug_token` endpoint. For token expiration, the API returns an `expires_at` timestamp field. However, this field behaves in a special way:

1. **Normal expiring tokens**: For tokens with a regular expiration date, `expires_at` contains a Unix timestamp representing when the token will expire.

2. **Long-lived tokens**: For tokens that don't expire (long-lived tokens), Facebook sets `expires_at` to `0`.

3. **Invalid timestamps**: In some rare cases, tokens might have very small timestamp values (0 or 1) that would translate to dates around January 1, 1970 (Unix epoch).

## How Our Application Handles This

In our application:

1. The `FacebookToken.get_expiration_date()` method converts all expiration timestamps to datetime objects, regardless of their value.
2. For long-lived tokens with `expires_at: 0`, this results in a date around January 1, 1970 (the Unix epoch).
3. The CLI displays this date as is, without any special handling for timestamps of 0 or 1.

This approach was chosen for the following reasons:

1. **Transparency**: Displaying the actual timestamp as a date provides transparency about what the Facebook API returns.
2. **Consistency**: All timestamps are handled in the same way, without special cases.
3. **Accuracy**: The date shown directly corresponds to the timestamp value returned by the API.

## Example API Response

Here's an example of what the Facebook API returns for a long-lived token:

```json
{
    "data": {
        "app_id": "1243594414131388",
        "type": "USER",
        "application": "INPOST",
        "data_access_expires_at": 1761860330,
        "expires_at": 0,
        "is_valid": true,
        "issued_at": 1753418653,
        "scopes": [
            "pages_show_list",
            "business_management",
            "instagram_basic",
            "instagram_content_publish",
            "public_profile"
        ],
        "user_id": "122125711268905986"
    }
}
```

Notice the `"expires_at": 0` field, which indicates this is a long-lived token that doesn't expire.

## Technical Implementation

The relevant code that handles this logic is in the `get_expiration_date()` method of the `FacebookToken` class:

```python
# Simplified version of the code in instapost/facebook/token.py
def get_expiration_date(self):
    """Get the token expiration date."""
    # First check if we have debug info from Facebook API
    if not hasattr(self, '_debug_info') or self._debug_info is None:
        raise Exception("Token must be validated before checking expiration")
        
    # Check if the token has an expiration time
    if "expires_at" not in self._debug_info:
        # Some tokens don't expire
        return None
        
    # Get the expiration timestamp
    expires_at = self._debug_info["expires_at"]
    
    # Convert to datetime - display all timestamps as is, even if they're 0 or 1
    from datetime import datetime
    return datetime.fromtimestamp(expires_at)
```

And in the CLI, this is handled by:

```python
# Simplified version of the code in instapost/cli.py (token_info command)
# Display expiration date if available
def display_expiration(token_data):
    # Get the expiration date from the token data
    expires_at = token_data.get('expires_at')
    
    # If we have an expiration date, show it
    if expires_at:
        print(f"Expires At: {expires_at}")
    else:
        # If expiration date is None (token doesn't have an expires_at field), show "Not available"
        print("Expires At: Not available")
```