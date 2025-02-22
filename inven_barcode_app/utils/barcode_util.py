import base64
from io import BytesIO
import barcode
import re

def generate_barcode_image(value):
    # Create the barcode
    barcode_class = barcode.get_barcode_class('code128')
    code128 = barcode_class(value)

    # Generate barcode as PNG
    buffer = BytesIO()
    code128.write(buffer, options={"write_text": False})  # Don't write text under the barcode

    # Save the image to the binary field as base64
    value = base64.b64encode(buffer.getvalue())
    buffer.close()
    
    return value

def extract_number_from_barcode(prefix, value):
    # Use the variable `prefix` in the regex pattern
    pattern = rf'{re.escape(prefix)}(\d+)'  # Escape the prefix to handle special characters if any
    match = re.search(pattern, value)
    if match:
        return int(match.group(1))  # Extract and convert the number to an integer
    return None  # Return None if no match is found