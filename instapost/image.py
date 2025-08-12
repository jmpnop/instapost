import os
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Directory to save images
IMAGES_DIR = "images"


def generate_noise_image():
    """Generate an image with noise and timestamp text, save to images/ with timestamp filename."""
    # Create images directory if not exists
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Get current timestamp for filename and text
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Generate noise image
    noise = np.random.rand(200, 200, 3)  # Simple RGB noise image
    fig, ax = plt.subplots()
    ax.imshow(noise)
    ax.text(10, 20, text, color='white', fontsize=12, bbox=dict(facecolor='black', alpha=0.5))
    ax.axis('off')

    # Save file
    file_path = os.path.join(IMAGES_DIR, f"{timestamp}.png")
    plt.savefig(file_path, bbox_inches='tight', pad_inches=0)
    plt.close(fig)

    print(f"Generated image: {file_path}")


if __name__ == "__main__":
    generate_noise_image()