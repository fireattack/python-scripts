from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def trim_image(img):
    gray_img = img.convert('L')
    img_array = np.array(gray_img)
    mask = img_array < 240
    coords = np.argwhere(mask)
    y0, x0 = coords.min(axis=0)
    y1, x1 = coords.max(axis=0) + 1
    trimmed = img.crop((x0, y0, x1, y1))
    return trimmed


def make_text_image(text, width, height, inital_fontsize=12, background_color=(0, 0, 0), font=None):
    if font is None:
        source_sans = Path(__file__).parent / 'SourceHanSans-Regular.otf'
        if source_sans.exists():
            font = str(source_sans)
        else:
            font = 'msyh.ttc' # fallback

    stroke_width = max(inital_fontsize//25, 1)

    img = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(img)

    fontsize = inital_fontsize
    while True:
        font_obj = ImageFont.truetype(font, fontsize)
        _, _, text_wdith, text_height = draw.textbbox((0, 0), text, font=font_obj)
        if text_wdith > width * 0.95 or text_height > height * 0.95:
            fontsize -= 1
        else:
            break

    draw.text(((width // 2, height // 2)), text, fill="white", font=font_obj, stroke_fill='black', stroke_width=stroke_width, anchor="mm", align="center")
    return img


def vertical_stack(images, background_color=(0, 0, 0)):
    widths, heights = zip(*(i.size for i in images))

    total_height = sum(heights)
    max_width = max(widths)

    new_im = Image.new('RGB', (max_width, total_height), background_color)

    y_offset = 0
    for im in images:
        x_offset = (max_width - im.size[0]) // 2
        new_im.paste(im, (x_offset, y_offset))
        y_offset += im.size[1]
    return new_im

def horizontal_stack(images, background_color=(0, 0, 0)):
    widths, heights = zip(*(i.size for i in images))

    total_width = sum(widths)
    max_height = max(heights)

    new_im = Image.new('RGB', (total_width, max_height), background_color)

    x_offset = 0
    for im in images:
        y_offset = (max_height - im.size[1]) // 2
        new_im.paste(im, (x_offset, y_offset))
        x_offset += im.size[0]
    return new_im

def fit_image_into_box(image, width, height, background_color=(0, 0, 0)):
    width_scaling_factor = width / image.width
    height_scaling_factor = height / image.height

    scaling_factor = min(width_scaling_factor, height_scaling_factor)

    new_width = int(image.width * scaling_factor)
    new_height = int(image.height * scaling_factor)

    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    box_background = Image.new("RGB", (width, height), background_color)  # You can set the background color as needed

    x_offset = (width - resized_image.width) // 2
    y_offset = (height - resized_image.height) // 2

    box_background.paste(resized_image, (x_offset, y_offset))

    return box_background