import os
import requests
from PIL import Image
from io import BytesIO
import streamlit as st
import boto3
import urllib
from pathlib import Path
from twilio.rest import Client
from clarifai.client.model import Model
import base64
import re
import shutil
import json
import time


# Fetch secrets from st.secrets
EBAY_AFFILIATE_ID = st.secrets["EBAY_AFFILIATE_ID"]
TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_NUMBER = st.secrets["TWILIO_NUMBER"]
CLARIFAI_PAT = st.secrets["CLARIFAI_PAT"]
FOLDER_PATH =  "twilio_pics"
CONCEPT_PATH = st.secrets["CONCEPT_PATH"]
THRESHOLD = .8  # Default to 0.8 if not set
S3_BUCKET_NAME = st.secrets["S3_BUCKET_NAME"]
EBAY_API_ENDPOINT = st.secrets["EBAY_API_ENDPOINT"]
EBAY_APP_ID = st.secrets["EBAY_APP_ID"]
EBAY_DEV_ID = st.secrets["EBAY_DEV_ID"]
EBAY_CERT_ID = st.secrets["EBAY_CERT_ID"]
AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"] 
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]

# Mapping of concepts to eBay category IDs
# Updated mapping of (gender, concept) to eBay category IDs
CONCEPT_TO_CATEGORY = {
    ("women", "bag"): "169291",  # Bags, purses, and backpacks - unisex
    ("men", "bag"): "169291",  # Bags, purses, and backpacks - unisex
    ("men", "belt"): "2993",  # Belts - men's accessories
    ("women", "belt"): "3003",  # Belts - women's accessories
    ("men", "bowtie"): "15662",  # Bowties - men's formalwear
    ("men", "bracelet"): "137835",  # Bracelets - men's jewelry
    ("women", "bracelet"): "164315",  # Bracelets - women's jewelry
    ("women", "dress"): "63861",  # Dresses - women's clothing
    ("men", "earrings"): "137856",  # Earrings - men's jewelry
    ("women", "earrings"): "164321",  # Earrings - women's jewelry
    ("women", "glasses"): "180957",  # Eyeglasses - unisex
    ("men", "glasses"): "180957",  # Eyeglasses - unisex
    ("men", "gloves"): "52347",  # Gloves - men's accessories
    ("women", "gloves"): "105559",  # Gloves - women's accessories
    ("women", "hair clip"): "110627",  # Hair accessories - women's accessories
    ("men", "hat"): "52365",  # Hats - men's hats
    ("women", "hat"): "3004",  # Hats - women's hats
    ("women", "headband"): "163628",  # Headbands - women's accessories
    ("women", "hosiery"): "11511",  # Hosiery and socks - women's clothing
    ("men", "hosiery"): "4250",  # Socks - men's clothing
    ("women", "jumpsuit"): "3009",  # Jumpsuits - women's clothing
    ("men", "jumpsuit"): "57988",  # Jumpsuits - men's clothing
    ("men", "mittens"): "52347",  # Mittens - men's accessories
    ("women", "mittens"): "105559",  # Mittens - women's accessories
    ("men", "necklace"): "137860",  # Necklaces - men's jewelry
    ("women", "necklace"): "164329",  # Necklaces - women's jewelry
    ("men", "necktie"): "15662",  # Ties and neckties - men's formalwear
    ("men", "outerwear"): "57988",  # Outerwear - men's clothing
    ("women", "outerwear"): "63862",  # Outerwear - women's clothing
    ("men", "pants"): "57989",  # Pants - men's clothing
    ("women", "pants"): "63863",  # Pants - women's clothing
    ("women", "pin/brooch"): "110626",  # Pins and brooches - women's accessories
    ("men", "pocket square"): "15662",  # Pocket squares - men's formalwear
    ("men", "ring"): "137856",  # Rings - men's jewelry
    ("women", "ring"): "164343",  # Rings - women's jewelry
    ("women", "romper"): "63861",  # Rompers - women's clothing
    ("men", "scarf"): "52366",  # Scarves - men's accessories
    ("women", "scarf"): "45238",  # Scarves - women's accessories
    ("men", "shoes"): "93427",  # Shoes - men's shoes
    ("women", "shoes"): "3034",  # Shoes - women's shoes
    ("men", "shorts"): "15689",  # Shorts - men's clothing
    ("women", "shorts"): "11555",  # Shorts - women's clothing
    ("women", "skirt"): "63864",  # Skirts - women's clothing
    ("men", "socks"): "4250",  # Socks - men's clothing
    ("women", "socks"): "11511",  # Socks - women's clothing
    ("men", "sunglasses"): "179247",  # Sunglasses - unisex
    ("women", "sunglasses"): "179247",  # Sunglasses - unisex
    ("men", "suspenders"): "15662",  # Suspenders - men's accessories
    ("men", "swimwear"): "15690",  # Swimwear - men's swimwear
    ("women", "swimwear"): "63867",  # Swimwear - women's swimwear
    ("men", "tie clip"): "15662",  # Tie clips and accessories - men's formalwear
    ("women", "top"): "53159",  # Tops - women's clothing
    ("men", "top"): "1059",  # Tops - men's clothing
    ("men", "vest"): "15691",  # Vests - men's clothing
    ("women", "vest"): "63866",  # Vests - women's clothing
    ("men", "watch"): "31387",  # Watches - men's accessories
    ("women", "watch"): "31387",  # Watches - women's accessories
    ("men", "t-shirt"): "15687",  # T-shirts - men's clothing
    ("women", "t-shirt"): "15724",  # T-shirts - women's clothing
    ("men", "jeans"): "11483",  # Jeans - men's clothing
    ("women", "jeans"): "11554",  # Jeans - women's clothing
    ("men", "jacket"): "57988",  # Jackets - men's clothing
    ("women", "jacket"): "63862",  # Jackets - women's clothing
    ("men", "coat"): "57988",  # Coats - men's clothing
    ("women", "coat"): "63862",  # Coats - women's clothing
    ("men", "suit"): "3001",  # Suits - men's formalwear
    ("women", "suit"): "63865",  # Suits - women's formalwear
    ("men", "sweater"): "11484",  # Sweaters - men's clothing
    ("women", "sweater"): "63866",  # Sweaters - women's clothing
    ("women", "blouse"): "53159",  # Blouses - women's clothing
    ("men", "hoodie"): "11484",  # Hoodies - men's clothing
    ("women", "hoodie"): "63866",  # Hoodies - women's clothing
    ("women", "cardigan"): "63866",  # Cardigans - women's clothing
    ("men", "cardigan"): "11484",  # Cardigans - men's clothing
    ("women", "leggings"): "169001",  # Leggings - women's clothing
    ("women", "bikini"): "63867",  # Bikinis - women's swimwear
    ("women", "gown"): "15720",  # Gowns - women's formalwear
    ("men", "cape"): "57988",  # Capes - men's clothing
    ("women", "cape"): "63862",  # Capes - women's clothing
    ("men", "mask"): "183477",  # Masks - unisex accessories
    ("women", "mask"): "183477",  # Masks - unisex accessories
    ("men", "overalls"): "57988",  # Overalls - men's clothing
    ("women", "overalls"): "11554",  # Overalls - women's clothing
    ("men", "poncho"): "57988",  # Ponchos - men's clothing
    ("women", "poncho"): "63862",  # Ponchos - women's clothing
    ("women", "sarong"): "63867",  # Sarongs - women's swimwear
    ("women", "shawl"): "45238",  # Shawls - women's accessories
    ("men", "sleepwear"): "11510",  # Sleepwear - men's clothing
    ("women", "sleepwear"): "63861",  # Sleepwear - women's clothing
    ("men", "tracksuit"): "15692",  # Tracksuits - men's clothing
    ("women", "tracksuit"): "11554",  # Tracksuits - women's clothing
    ("men", "trousers"): "57989",  # Trousers - men's clothing
    ("women", "trousers"): "63863",  # Trousers - women's clothing
    ("men", "backpack"): "169291",  # Backpacks - unisex accessories
    ("women", "backpack"): "169291",  # Backpacks - unisex accessories
    ("women", "bandeau"): "63867",  # Bandeaus - women's clothing
    ("men", "beanie"): "52382",  # Beanies - unisex hats
    ("women", "beanie"): "52382",  # Beanies - unisex hats
    ("men", "beret"): "52382",  # Berets - unisex hats
    ("women", "beret"): "52382",  # Berets - unisex hats
    ("men", "bermuda shorts"): "15689",  # Bermuda shorts - men's clothing
    ("women", "bermuda shorts"): "11555",  # Bermuda shorts - women's clothing
    ("men", "biker jacket"): "57988",  # Biker jackets - men's clothing
    ("women", "biker jacket"): "63862",  # Biker jackets - women's clothing
    ("women", "bikini bottom"): "63867",  # Bikini bottoms - women's swimwear
    ("women", "bikini set"): "63867",  # Bikini sets - women's swimwear
    ("women", "bikini top"): "63867",  # Bikini tops - women's swimwear
    ("men", "blazer"): "3002",  # Blazers - men's formalwear
    ("women", "blazer"): "63865",  # Blazers - women's formalwear
    ("women", "boatneck/bateau"): "53159",  # Boatneck tops - women's clothing
    ("men", "bomber"): "57988",  # Bomber jackets - men's clothing
    ("women", "bomber"): "63862",  # Bomber jackets - women's clothing
    ("women", "booties"): "3034",  # Booties - women's shoes
    ("women", "bra"): "63853",  # Bras - women's undergarments
    ("unisex", "bucket hat"): "52382",  # Bucket hats - unisex hats
    ("women", "camisole"): "11514",  # Camisoles - women's clothing
    ("men", "cape/poncho"): "57988",  # Capes and ponchos - men's clothing
    ("women", "cape/poncho"): "63862",  # Capes and ponchos - women's clothing
    ("women", "capris"): "63863",  # Capris - women's clothing
    ("women", "capsleeve"): "53159",  # Capsleeve tops - women's clothing
    ("men", "cargo pants"): "57989",  # Cargo pants - men's clothing
    ("women", "cargo pants"): "63863",  # Cargo pants - women's clothing
    ("men", "cargo shorts"): "15689",  # Cargo shorts - men's clothing
    ("women", "cargo shorts"): "11555",  # Cargo shorts - women's clothing
    ("men", "denim jacket"): "57988",  # Denim jackets - men's clothing
    ("women", "denim jacket"): "63862",  # Denim jackets - women's clothing
    ("men", "duffle coat"): "57988",  # Duffle coats - men's clothing
    ("women", "duffle coat"): "63862",  # Duffle coats - women's clothing
    ("unisex", "fedora"): "52382",  # Fedoras - unisex hats
    ("men", "field jacket"): "57988",  # Field jackets - men's clothing
    ("women", "field jacket"): "63862",  # Field jackets - women's clothing
    ("women", "flats"): "3034",  # Flats - women's shoes
    ("men", "fleece"): "11484",  # Fleece clothing - men's clothing
    ("women", "fleece"): "63866",  # Fleece clothing - women's clothing
    ("men", "flip-flops"): "11504",  # Flip-flops - men's shoes
    ("women", "flip-flops"): "3034",  # Flip-flops - women's shoes
    ("women", "floppy hat"): "3004",  # Floppy hats - women's hats
    ("women", "halter"): "11514",  # Halter tops - women's clothing
    ("men", "loafers"): "93427",  # Loafers - men's shoes
    ("women", "loafers"): "3034",  # Loafers - women's shoes
    ("women", "maxi dress"): "63861",  # Maxi dresses - women's clothing
    ("women", "maxi skirt"): "63864",  # Maxi skirts - women's clothing
    ("women", "midi dress"): "63861",  # Midi dresses - women's clothing
    ("women", "midi skirt"): "63864",  # Midi skirts - women's clothing
    ("women", "mini dress"): "63861",  # Mini dresses - women's clothing
    ("women", "mini skirt"): "63864",  # Mini skirts - women's clothing
    ("women", "mockneck"): "53159",  # Mockneck tops - women's clothing
    ("women", "mules"): "3034",  # Mules - women's shoes
    ("unisex", "newsboy/flat cap"): "52382",  # Newsboy caps - unisex hats
    ("women", "one piece swimsuit"): "63867",  # One-piece swimsuits - women's swimwear
    ("men", "oxfords"): "93427",  # Oxfords - men's shoes
    ("women", "oxfords"): "3034",  # Oxfords - women's shoes
    ("men", "pajamas"): "11510",  # Pajamas - men's sleepwear
    ("women", "pajamas"): "63861",  # Pajamas - women's sleepwear
    ("men", "parka"): "57988",  # Parkas - men's clothing
    ("women", "parka"): "63862",  # Parkas - women's clothing
    ("men", "peacoat"): "57988",  # Peacoats - men's clothing
    ("women", "peacoat"): "63862",  # Peacoats - women's clothing
    ("men", "polo"): "1059",  # Polo shirts - men's clothing
    ("women", "polo"): "53159",  # Polo shirts - women's clothing
    ("men", "puffer coat"): "57988",  # Puffer coats - men's clothing
    ("women", "puffer coat"): "63862",  # Puffer coats - women's clothing
    ("men", "puffer vest"): "15691",  # Puffer vests - men's clothing
    ("women", "puffer vest"): "63866",  # Puffer vests - women's clothing
    ("women", "pumps"): "3034",  # Pumps - women's shoes
    ("men", "rain boots"): "93427",  # Rain boots - men's shoes
    ("women", "rain boots"): "3034",  # Rain boots - women's shoes
    ("men", "sandals"): "11504",  # Sandals - men's shoes
    ("women", "sandals"): "3034",  # Sandals - women's shoes
    ("women", "satchel"): "169291",  # Satchels - women's bags
    ("men", "shirt"): "1059",  # Shirts - men's clothing
    ("women", "shirt"): "53159",  # Shirts - women's clothing
    ("men", "short-sleeve"): "1059",  # Short-sleeve shirts - men's clothing
    ("women", "short-sleeve"): "53159",  # Short-sleeve tops - women's clothing
    ("women", "shortalls"): "11554",  # Shortalls - women's clothing
    ("women", "sleeveless"): "53159",  # Sleeveless tops - women's clothing
    ("men", "sleeveless"): "1059",  # Sleeveless shirts - men's clothing
    ("women", "shoulder bag"): "169291",  # Shoulder bags - women's accessories
    ("men", "sneakers"): "93427",  # Sneakers - men's shoes
    ("women", "sneakers"): "3034",  # Sneakers - women's shoes
    ("women", "spaghetti strap"): "11514",  # Spaghetti strap tops - women's clothing
    ("women", "strapless"): "53159",  # Strapless tops - women's clothing
    ("men", "suit jacketsuit pants"): "3001",  # Suit jackets and pants - men's formalwear
    ("men", "sweater vest"): "11484",  # Sweater vests - men's clothing
    ("women", "sweater vest"): "63866",  # Sweater vests - women's clothing
    ("men", "sweatpants"): "11510",  # Sweatpants - men's clothing
    ("women", "sweatpants"): "11554",  # Sweatpants - women's clothing
    ("men", "sweatshirt"): "11484",  # Sweatshirts - men's clothing
    ("women", "sweatshirt"): "63866",  # Sweatshirts - women's clothing
    ("men", "swim trunks"): "15690",  # Swim trunks - men's swimwear
    ("men", "tank"): "15692",  # Tank tops - men's clothing
    ("women", "tank"): "11514",  # Tank tops - women's clothing
    ("women", "tote bag"): "169291",  # Tote bags - women's accessories
    ("unisex", "trapper hat"): "52382",  # Trapper hats - unisex hats
    ("men", "trenchcoat"): "57988",  # Trenchcoats - men's clothing
    ("women", "trenchcoat"): "63862",  # Trenchcoats - women's clothing
    ("men", "waistcoat"): "15691",  # Waistcoats - men's formalwear
    ("women", "waistcoat"): "63865",  # Waistcoats - women's formalwear
    ("women", "wedges"): "3034",  # Wedge shoes - women's shoes
    ("women", "wide leg pants"): "63863",  # Wide leg pants - women's clothing
    ("women", "wristlet and clutch"): "169291",  # Wristlets and clutches - women's accessories
}



# Define your default category
DEFAULT_CATEGORY = "11450"

# Function to get category with a default fallback
def get_category(concept):
    return CONCEPT_TO_CATEGORY.get(concept, DEFAULT_CATEGORY)

# Stylistic items to be passed into the search
STYLISTIC_ITEMS = [
    "3/4 sleeve",
    "argyle",
    "asymmetric/one-shoulder",
    "cableknit",
    "camouflage",
    "cheetah",
    "chelsea boots",
    "chevron/zig-zag",
    "cowl neck",
    "crewneck",
    "crop top",
    "culottes",
    "d'orsay",
    "damask",
    "dangle earrings",
    "eyelet",
    "fair isle",
    "floral",
    "fur",
    "gingham",
    "giraffe",
    "glitter",
    "graphic",
    "hair tie",
    "heart",
    "henley",
    "herringbone",
    "long-sleeve",
    "mockneck",
    "off-shoulder",
    "paisley",
    "patchwork",
    "peter pan collar",
    "pleated",
    "polka dot",
    "puff sleeve",
    "ruffle",
    "scalloped",
    "scoopneck",
    "sequin",
    "shawl collar",
    "sqaureneck",
    "star",
    "stripes",
    "stud earrings",
    "suede",
    "sweetheart",
    "tartan/plaid",
    "tattersall",
    "tie-dye/shibori",
    "toile",
    "tortoise",
    "tropical",
    "tulle",
    "turtleneck",
    "v-neck",
    "velvet",
    "windowpane",
    "zebra"
]

# Initialize clients
def init_twilio_client():
    st.success('Twilio initialized!', icon="✅")
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def init_clarifai_model(key):
    model_url = "https://clarifai.com/clarifai/main/models/apparel-detection"
    st.success('Clarifai initialized!', icon="✅")
    return Model(url=model_url, pat=key)

def init_clarifai_labels(key):
    st.success('Clarifai labeling initialized!', icon="✅")
    model_url = "https://clarifai.com/clarifai/main/models/apparel-classification-v2"
    return Model(url=model_url, pat=key)
 
def init_clarifai_face(key):
    st.success('Clarifai face initialized!', icon="✅")
    model_url = "https://clarifai.com/clarifai/main/models/face-detection"
    return Model(url=model_url, pat=key)

def init_clarifai_gender(key):
    st.success('Clarifai gender initialized!', icon="✅")
    model_url = "https://clarifai.com/clarifai/main/models/gender-demographics-recognition"
    return Model(url=model_url, pat=key)   

# Twilio message processing
def create_directory_for_number(directory_path):
    if not directory_path.exists():
        directory_path.mkdir(parents=True, exist_ok=True)

def download_media(media_list, from_number, msg_sid):
    media_urls, file_paths, file_names = [], [], []
    for i, media in enumerate(media_list):
        media_url = f"https://api.twilio.com{media.uri.replace('.json', '')}"
        response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        if response.status_code == 200:
            file_path, file_name = save_media(response, from_number, msg_sid, i)
            media_urls.append(media_url)
            file_paths.append(file_path)
            file_names.append(file_name)
    return media_urls, file_paths, file_names

def save_media(response, from_number, msg_sid, media_index):
    content_type = response.headers['Content-Type']
    extension = "png" if "image" in content_type else content_type.split('/')[1]
    file_path = os.path.join(FOLDER_PATH, from_number, f"{msg_sid}_{media_index}.{extension}")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    file_name = file_path.split('/')[-1]
    if "image" in content_type:
        image = Image.open(BytesIO(response.content)).convert("RGBA")
        image.save(file_path, "PNG")
    else:
        with open(file_path, "wb") as file:
            file.write(response.content)
    return file_path, file_name

def process_twilio_messages(client, twilio_number):
    messages = client.messages.list(to=twilio_number)
    # Find the most recent message with media
    recent_message = None
    for msg in messages:
        if int(msg.num_media) > 0:
            recent_message = msg
            break  # Since messages are in descending order, break after the first message with media
    if not recent_message:
        st.error("No messages with media found.")
        return {}
    message_data = {}
    from_number = recent_message.from_
    directory_path = Path(f"{FOLDER_PATH}/{from_number}")
    create_directory_for_number(directory_path)
    media_urls, file_paths, file_names = [], [], []
    media_urls, file_paths, file_names = download_media(client.messages(recent_message.sid).media.list(), from_number, recent_message.sid)
    message_data[from_number] = [{
        "media_urls": media_urls,
        "media_path": file_paths,
        "file_names": file_names
    }]
    return message_data

# Image listing and S3 integration
def list_image_paths(folder_path, phone_number):
    image_data = []
    subfolder_path = os.path.join(folder_path, phone_number)
    if os.path.isdir(subfolder_path):
        for image_file in os.listdir(subfolder_path):
            image_path = os.path.join(subfolder_path, image_file)
            if image_path.endswith(('.png', '.jpg', '.jpeg')):
                image_data.append({"phone_number": phone_number, "image_path": image_path, "url": ""})
            break
    st.write(image_data)
    return image_data

def s3_write_urls(image_data):
    s3 = boto3.client('s3')
    for data in image_data:
        path, phone = data['image_path'], data['phone_number']
        file_name = path.split('/')[-1]
        s3.upload_file(path, S3_BUCKET_NAME, file_name)
        s3.put_object_tagging(
            Bucket=S3_BUCKET_NAME,
            Key=file_name,
            Tagging={
                'TagSet': [
                    {'Key': 'PhoneNumber', 'Value': phone}
                ]
            }
        )
        data["url"] = get_public_url(S3_BUCKET_NAME, file_name)
    return image_data

def get_public_url(bucket_name, object_key):
    encoded_key = urllib.parse.quote(object_key)
    return f"https://{bucket_name}.s3.amazonaws.com/{encoded_key}"

# Image analysis and prediction
def analyze_images(image_data, model):
    for data in image_data:
        url = data['url']
        try:
            prediction_response = model.predict_by_url(url, input_type="image")
            if prediction_response.outputs:
                data["prediction"] = prediction_response
        except Exception as e:
            st.write(f"Error occurred: {str(e)}")
    return image_data



# Image analysis and prediction
from io import BytesIO

# Image analysis and prediction
# Image analysis and prediction
def add_tags(concepts, model):
    for data in concepts:
        image_source = data['concept_image']  # This could be a file path or URL

        # Display the image in Streamlit
        # Load the image into a PIL Image object
        if isinstance(image_source, str):
            if image_source.startswith('http'):
                # Load image from URL
                response = requests.get(image_source)
                image = Image.open(BytesIO(response.content))
            else:
                # Load image from file path
                image = Image.open(image_source)
        else:
            # If image_source is already an image object
            image = image_source

        # Convert the image to bytes using BytesIO
        image_bytes_io = BytesIO()
        image.save(image_bytes_io, format="PNG")  # Adjust the format if necessary
        image_bytes = image_bytes_io.getvalue()

        # Base64-encode the image bytes
        image_base64_bytes = base64.b64encode(image_bytes)
        # Decode to UTF-8 string
        image_base64_string = image_base64_bytes.decode('utf-8')

        # Optionally, display the Base64 string (careful, it's long)
        # st.write(image_base64_string)

        try:
            # Remove the incorrect input_type="text" argument
            # Pass the correct bytes data to predict_by_bytes
            prediction_response = model.predict_by_bytes(image_bytes, input_type='image')
            if prediction_response.outputs:

                concepts_list = prediction_response.outputs[0].data.concepts
                # Save the concepts to data["tags"]
                data["tags"]=concepts_list
                #st.write (concepts_list)
        except Exception as e:
            st.write(f"Error occurred: {str(e)}")
    return concepts

# User interaction and concept extraction
def extract_user_concepts(prediction_responses, user_phone):
    concepts = []
    for data in prediction_responses:
        if data['phone_number'] == user_phone:
            st.write("You shared this photo: ", data['url'])
            if data['prediction'].outputs:
                regions = data['prediction'].outputs[0].data.regions
                for region in regions:
                    top_row = region.region_info.bounding_box.top_row
                    left_col = region.region_info.bounding_box.left_col
                    bottom_row = region.region_info.bounding_box.bottom_row
                    right_col = region.region_info.bounding_box.right_col
                    for concept in region.data.concepts:
                        if concept.value > THRESHOLD:
                            image_path = data['image_path']
                            st.write(f'image path:{image_path}')
                            concept_image = crop_image(image_path, top_row, left_col, bottom_row, right_col)
                            concepts.append({
                                "concept_image": concept_image,
                                "concept_name": concept.name.lower()
                            })
    return concepts

def extract_concepts(text):
    # Using regex to find all occurrences of 'name: "<value>"'
    matches = re.findall(r'name: \"(.*?)\"', text)
    if matches:
        return matches[0]
    return None

def get_gender(url_image_data,face_model,gender_model):
    for data in url_image_data:
        url = data['url']
        face_data = []
        gender = []
        try:
            prediction_response = face_model.predict_by_url(url, input_type="image")
            if prediction_response.outputs:
                face_data.append({"prediction": prediction_response})
                #st.write(face_data[0]['prediction'])
                if face_data[0]['prediction'].outputs:
                    regions = face_data[0]['prediction'].outputs[0].data.regions
                    for region in regions:
                        top_row = region.region_info.bounding_box.top_row
                        left_col = region.region_info.bounding_box.left_col
                        bottom_row = region.region_info.bounding_box.bottom_row
                        right_col = region.region_info.bounding_box.right_col
                        for concept in region.data.concepts:
                            if concept.value > THRESHOLD:
                                image_path = data['image_path']
                                concept_image = crop_image(image_path, top_row, left_col, bottom_row, right_col)
                                image_bytes_io = BytesIO()
                                concept_image.save(image_bytes_io, format="PNG")  # Adjust the format if necessary
                                image_bytes = image_bytes_io.getvalue()

                                # Base64-encode the image bytes
                                image_base64_bytes = base64.b64encode(image_bytes)
                                # Decode to UTF-8 string
                                image_base64_string = image_base64_bytes.decode('utf-8')

                                try:
                                    prediction_response = gender_model.predict_by_bytes(image_bytes, input_type='image')
                                    if prediction_response.outputs:
                                        concepts_list = prediction_response.outputs[0].data.concepts
                                        gender.append(concepts_list)
                                        #st.write(gender)
                                        # Determine the most likely gender
                                        top_gender = max(concepts_list, key=lambda concept: concept.value).name
                                        st.write(f"Top gender: {top_gender}")
                                        if top_gender == 'Masculine':
                                            return 'men'
                                        else:
                                            return 'women'
                                except Exception as e:
                                    st.write(f"Error occurred: {str(e)}")
        except Exception as e:
            st.write(f'Error occurred: {e}')
            return 'women'


def crop_image(image_path, top_row, left_col, bottom_row, right_col):
    concept_image = Image.open(image_path)
    width, height = concept_image.size
    crop = (left_col * width, top_row * height, right_col * width, bottom_row * height)
    return concept_image.crop(crop)

# eBay Vision Search API integration with category mapping
def search_ebay_with_concepts(concepts, ebay_access_token, affiliate_id,gender):
    headers = {
        "Authorization": f"Bearer {ebay_access_token}",
        "Content-Type": "application/json"
    }
    for concept in concepts:
        image = concept["concept_image"]
        image_bytes = BytesIO()
        image.save(image_bytes, format='PNG')
        image_bytes = image_bytes.getvalue()
        data = {
            "image": base64.b64encode(image_bytes).decode('utf-8')
        }
        concept_name = gender,extract_concepts(str(concept['tags']))
        st.write(concept_name)
        category_id = get_category(concept_name)
        if category_id:
            endpoint = f"{EBAY_API_ENDPOINT}?q={concept_name}&category_ids={category_id}&aspect_filter=categoryId:{category_id}"
        else:
            endpoint = EBAY_API_ENDPOINT
            st.warning(f"No category mapping found for concept '{concept_name}'. Using default search.")
        attempts = 3
        for attempt in range(attempts):
            response = requests.post(
                endpoint,
                headers=headers,
                data=json.dumps(data)
            )
            if response.status_code == 200:
                break
            elif response.status_code >= 500:
                st.write(f"eBay API request failed: {response.status_code} - {response.text}. Retrying ({attempt + 1}/{attempts})...")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                break
        if response.status_code == 200:
            ebay_response = response.json()
            item_summaries = ebay_response.get('itemSummaries', [])
            top_links = []
            for item in item_summaries:  
                correct_category = False
                for subcat in item['categories']:
                    if category_id == subcat['categoryId']:
                        correct_category = True
                item_url = item.get('itemWebUrl')
                if correct_category and len(top_links) < 3:
                    # Add affiliate ID to the URL
                    affiliate_url = f"{item_url}&mkcid=1&mkrid={affiliate_id}&campid={affiliate_id}&toolid=10001"
                    top_links.append(affiliate_url)
            concept['top_links'] = top_links
        else:
            st.error(f"eBay API request failed: {response.status_code} - {response.text}")
            concept['top_links'] = []
    return concepts

# OAuth flow for eBay API
def ebay_oauth_flow():
    import base64
    import requests

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {base64.b64encode((EBAY_APP_ID + ':' + EBAY_CERT_ID).encode()).decode()}"
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope"
    }

    response = requests.post("https://api.ebay.com/identity/v1/oauth2/token", headers=headers, data=data)

    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get("access_token")
        st.success('eBay Authorized!', icon="✅")
        return access_token
    else:
        st.error(f"Failed to obtain eBay OAuth token: {response.status_code} - {response.text}")
        return None

def delete_photos(folder_path):
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        st.success("Photos have been deleted.", icon="✅")
    else:
        st.error("Folder does not exist.")

#sends the outputs back
def send_results_via_twilio(client, to_number, concepts):
    for concept in concepts:
        # Create message body for each concept
        concept_name = concept['concept_name']
        message_body = f"{concept_name.capitalize()}:\n"
        
        top_links = concept.get('top_links', [])
        if top_links:
            for i, link in enumerate(top_links, 1):
                message_body += f"{i}. {link}\n"
        else:
            message_body += "No links found.\n"
        
        # Try sending each message
        try:
            message = client.messages.create(
                body=message_body,
                from_=TWILIO_NUMBER,
                to=to_number
            )
            st.success(f"Results for {concept_name} sent via SMS to {to_number}", icon="✅")
        except Exception as e:
            st.error(f"Failed to send SMS for {concept_name}: {str(e)}")




def main():
    # Initialize clients and models
    client = init_twilio_client()
    detector_model = init_clarifai_model(CLARIFAI_PAT)
    label_model = init_clarifai_labels(CLARIFAI_PAT)
    face_model = init_clarifai_face(CLARIFAI_PAT)
    gender_model = init_clarifai_gender(CLARIFAI_PAT)
    # Obtain eBay OAuth token
    EBAY_ACCESS_TOKEN = ebay_oauth_flow()

    # Process messages and extract images
    message_data = process_twilio_messages(client, TWILIO_NUMBER)

    if not message_data:
        st.error("No messages with media to process.")
        return ""
    else:
        # Get the phone number from the message_data
        user_phone = list(message_data.keys())[0]

        # List image paths for the user
        image_data = list_image_paths(FOLDER_PATH, user_phone)
        url_image_data = s3_write_urls(image_data)
        st.success("Written to S3", icon="✅")

        # Analyze images using Clarifai model
        prediction_responses = analyze_images(url_image_data, detector_model)
        st.success("Predictions generated", icon="✅")

        gender = get_gender(url_image_data,face_model,gender_model)
        st.success(f"Gender is {gender}", icon="✅")

        # User interaction
        st.write(f"Processing images from phone number: {user_phone}")
        user_concepts = extract_user_concepts(prediction_responses, user_phone)
        st.success("Concepts analyzed", icon="✅")

        tagged_concepts=add_tags(user_concepts,label_model)
        st.success("Concepts tagged", icon="✅")

        # Send user concepts to eBay Vision Search API and get top 3 links
        if tagged_concepts:
            tagged_concepts = search_ebay_with_concepts(tagged_concepts, EBAY_ACCESS_TOKEN,EBAY_AFFILIATE_ID,gender)
            st.write("eBay Search Results:")
            for concept in tagged_concepts:
                concept_name = concept['concept_name']
                st.write(f"Top 3 eBay links for concept '{concept_name}':")
                #st.write(concept)
                # Display concept image and links in columns
                col1, col2 = st.columns([1, 3])
                with col1:
                    # Display concept image
                    st.image(concept['concept_image'], caption=concept_name, use_column_width=True)
                with col2:
                    # Display top 3 links
                    top_links = concept.get('top_links', [])
                    if top_links:
                        for link in top_links:
                            st.markdown(f"- [eBay Item Link]({link})")
                    else:
                        st.write("No links found.")
            send_results_via_twilio(client, user_phone, tagged_concepts)
        else:
            st.write("No concepts extracted from the image.")
        delete_photos(FOLDER_PATH)
        #st.write(message_data)
        return list(message_data.values())[0]
    # In the main section, after processing the concepts and eBay links:




    # Delete photos at the end of the program



# Main
if __name__ == "__main__":
    client = init_twilio_client()
    last_message = ""
    while True:
        other_data = process_twilio_messages(client, TWILIO_NUMBER)
        message_data = list(other_data.values())[0]
        #st.write (other_data)
        if message_data != last_message:
            last_message = main()
            message_data = last_message
