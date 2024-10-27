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
CONCEPT_TO_CATEGORY = {
    "bag": "169291",  # Bags, purses, and backpacks - unisex
    "belt": "2993",  # Belts - men's and women's accessories
    "bowtie": "15662",  # Ties and bowties - men's formalwear
    "bracelet": "10370",  # Bracelets - men's and women's jewelry
    "dress": "63861",  # Dresses - women's clothing
    "earrings": "10985",  # Earrings - women's and men's jewelry
    "glasses": "180957",  # Eyeglasses - unisex
    "gloves": "182108",  # Gloves - men's and women's accessories
    "hair clip": "110626",  # Hair accessories - women's accessories
    "hat": "52382",  # Hats - men's and women's hats
    "headband": "45220",  # Headbands - women's accessories
    "hosiery": "11511",  # Hosiery and socks - women's clothing
    "jumpsuit": "3009",  # Jumpsuits - women's clothing
    "mittens": "1069",  # Mittens - men's and women's accessories
    "necklace": "164329",  # Necklaces - men's and women's jewelry
    "necktie": "15662",  # Ties and neckties - men's formalwear
    "outerwear": "57988",  # Outerwear, including coats and jackets - men's and women's clothing
    "pants": "63863",  # Pants - men's and women's clothing
    "pin/brooch": "110626",  # Pins and brooches - women's accessories
    "pocket square": "15662",  # Ties and pocket squares - men's formalwear
    "ring": "67726",  # Rings - men's and women's jewelry
    "romper": "63861",  # Rompers - women's clothing
    "scarf": "45238",  # Scarves - men's and women's accessories
    "shoes": "63889",  # Shoes - men's and women's shoes
    "shorts": "11555",  # Shorts - men's and women's clothing
    "skirt": "63864",  # Skirts - women's clothing
    "socks": "11511",  # Socks - men's and women's clothing
    "sunglasses": "179247",  # Sunglasses - unisex
    "suspenders": "15662",  # Suspenders - men's accessories
    "swimwear": "63867",  # Swimwear - men's and women's swimwear
    "tie clip": "15662",  # Tie clips and accessories - men's formalwear
    "top": "53159",  # Tops - women's clothing
    "vest": "11510",  # Vests - men's and women's clothing
    "watch": "31387",  # Watches - men's and women's accessories
    "t-shirt": "15687",  # T-shirts - men's and women's clothing
    "jeans": "11483",  # Jeans - men's and women's clothing
    "jacket": "57988",  # Jackets - men's and women's clothing
    "coat": "57988",  # Coats - men's and women's clothing
    "suit": "3001",  # Suits - men's formalwear
    "sweater": "11484",  # Sweaters - men's and women's clothing
    "blouse": "53159",  # Blouses - women's clothing
    "hoodie": "11484",  # Hoodies - men's and women's clothing
    "cardigan": "11484",  # Cardigans - women's clothing
    "leggings": "169001",  # Leggings - women's clothing
    "bikini": "63867",  # Bikinis - women's swimwear
    "gown": "11554",  # Gowns - women's formalwear
    "cape": "11510",  # Capes - men's and women's clothing
    "mask": "183477",  # Masks - unisex accessories
    "overalls": "11554",  # Overalls - men's and women's clothing
    "poncho": "11510",  # Ponchos - men's and women's clothing
    "sarong": "63867",  # Sarongs - women's swimwear
    "shawl": "45238",  # Shawls - women's accessories
    "sleepwear": "63862",  # Sleepwear - men's and women's clothing
    "tracksuit": "11554",  # Tracksuits - men's and women's clothing
    "trousers": "63863",  # Trousers - men's and women's clothing
    "backpack": "169291",  # Backpacks - unisex accessories
    "bandeau": "63867",  # Bandeaus - women's clothing
    "beanie": "52382",  # Beanies - men's and women's hats
    "beret": "52382",  # Berets - men's and women's hats
    "bermuda shorts": "11555",  # Bermuda shorts - men's and women's clothing
    "biker jacket": "57988",  # Biker jackets - men's and women's clothing
    "bikini bottom": "63867",  # Bikini bottoms - women's swimwear
    "bikini set": "63867",  # Bikini sets - women's swimwear
    "bikini top": "63867",  # Bikini tops - women's swimwear
    "blazer": "3002",  # Blazers - men's and women's formalwear
    "boatneck/bateau": "53159",  # Boatneck or bateau tops - women's clothing
    "bomber": "57988",  # Bomber jackets - men's and women's clothing
    "booties": "63889",  # Booties - women's shoes
    "bra": "63853",  # Bras - women's undergarments
    "bucket hat": "52382",  # Bucket hats - men's and women's hats
    "camisole": "11514",  # Camisoles - women's clothing
    "cape/poncho": "11510",  # Capes and ponchos - men's and women's clothing
    "capris": "63863",  # Capris - women's clothing
    "capsleeve": "53159",  # Capsleeve tops - women's clothing
    "cargo pants": "11554",  # Cargo pants - men's and women's clothing
    "cargo shorts": "11555",  # Cargo shorts - men's and women's clothing
    "denim jacket": "57988",  # Denim jackets - men's and women's clothing
    "duffle coat": "57988",  # Duffle coats - men's and women's clothing
    "fedora": "52382",  # Fedoras - men's and women's hats
    "field jacket": "57988",  # Field jackets - men's and women's clothing
    "flats": "63889",  # Flats - women's shoes
    "fleece": "11484",  # Fleece clothing - men's and women's clothing
    "flip-flops": "11504",  # Flip-flops - men's and women's shoes
    "floppy hat": "52382",  # Floppy hats - women's hats
    "halter": "11514",  # Halter tops - women's clothing
    "loafers": "11504",  # Loafers - men's and women's shoes
    "maxi dress": "63861",  # Maxi dresses - women's clothing
    "maxi skirt": "63864",  # Maxi skirts - women's clothing
    "midi dress": "63861",  # Midi dresses - women's clothing
    "midi skirt": "63864",  # Midi skirts - women's clothing
    "mini dress": "63861",  # Mini dresses - women's clothing
    "mini skirt": "63864",  # Mini skirts - women's clothing
    "mockneck": "53159",  # Mockneck tops - women's clothing
    "mules": "11504",  # Mules - women's shoes
    "newsboy/flat cap": "52382",  # Newsboy or flat caps - men's and women's hats
    "one piece swimsuit": "63867",  # One-piece swimsuits - women's swimwear
    "oxfords": "11504",  # Oxford shoes - men's and women's shoes
    "pajamas": "63862",  # Pajamas - men's and women's sleepwear
    "parka": "57988",  # Parkas - men's and women's clothing
    "peacoat": "57988",  # Peacoats - men's and women's clothing
    "polo": "1059",  # Polo shirts - men's and women's clothing
    "puffer coat": "57988",  # Puffer coats - men's and women's clothing
    "puffer vest": "57988",  # Puffer vests - men's and women's clothing
    "pumps": "11504",  # Pumps - women's shoes
    "rain boots": "63889",  # Rain boots - men's and women's shoes
    "sandals": "11504",  # Sandals - men's and women's shoes
    "satchel": "169291",  # Satchels - men's and women's bags
    "shirt": "53159",  # Shirts - men's and women's clothing
    "short-sleeve": "53159",  # Short-sleeve tops - men's and women's clothing
    "shortalls": "11554",  # Shortalls - women's clothing
    "sleeveless":"53159", #tops - womens
    "shoulder bag": "169291",  # Shoulder bags - women's bags
    "sneakers": "11504",  # Sneakers - men's and women's shoes
    "spaghetti strap": "53159",  # Spaghetti strap tops - women's clothing
    "strapless": "53159",  # Strapless tops - women's clothing
    "suit jacketsuit pants": "3001",  # Suit jackets and pants - men's formalwear
    "sweater vest": "11484",  # Sweater vests - men's and women's clothing
    "sweatpants": "11554",  # Sweatpants - men's and women's clothing
    "sweatshirt": "11484",  # Sweatshirts - men's and women's clothing
    "swim trunks": "63867",  # Swim trunks - men's swimwear
    "tank": "11514",  # Tank tops - men's and women's clothing
    "tote bag": "169291",  # Tote bags - women's bags
    "trapper hat": "52382",  # Trapper hats - men's and women's hats
    "trenchcoat": "57988",  # Trenchcoats - men's and women's clothing
    "waistcoat": "11510",  # Waistcoats - men's and women's formalwear
    "wedges": "11504",  # Wedge shoes - women's shoes
    "wide leg pants": "63863",  # Wide leg pants - women's clothing
    "wristlet and clutch": "169291"  # Wristlets and clutches - women's accessories
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
    #os.makedirs(os.path.dirname(file_path), exist_ok=True)
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
        try:
            prediction_response = face_model.predict_by_url(url, input_type="image")
            if prediction_response.outputs:
                data["prediction"] = prediction_response
                st.write(data['prediction'])
        except Exception as e:
            st.write(f'Error occurred{e}')
    return 'null'


def crop_image(image_path, top_row, left_col, bottom_row, right_col):
    concept_image = Image.open(image_path)
    width, height = concept_image.size
    crop = (left_col * width, top_row * height, right_col * width, bottom_row * height)
    return concept_image.crop(crop)

# eBay Vision Search API integration with category mapping
def search_ebay_with_concepts(concepts, ebay_access_token, affiliate_id):
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
        concept_name = extract_concepts(str(concept['tags']))
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
        gender = get_gender(url_image_data,face_model,gender_model)
        st.success("Predictions generated", icon="✅")


        # User interaction
        st.write(f"Processing images from phone number: {user_phone}")
        user_concepts = extract_user_concepts(prediction_responses, user_phone)
        st.success("Concepts analyzed", icon="✅")

        tagged_concepts=add_tags(user_concepts,label_model)
        st.success("Concepts tagged", icon="✅")

        # Send user concepts to eBay Vision Search API and get top 3 links
        if tagged_concepts:
            tagged_concepts = search_ebay_with_concepts(tagged_concepts, EBAY_ACCESS_TOKEN,EBAY_AFFILIATE_ID)
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
