from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import json
import re

app = Flask(__name__)

# Setup Google Sheets API (initialize only once on startup)
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SHEET_ID = '1sVuQGZjHToaryPNNSOytHNZPnGHFqzc2XfbDGsOxRSI'
SHEET_NAME = 'pizza_price'

if not SERVICE_ACCOUNT_JSON:
    raise Exception("SERVICE_ACCOUNT_JSON not found in environment variables")

# Load service account credentials
creds_dict = json.loads(SERVICE_ACCOUNT_JSON)
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Load prices from sheet at startup
result = sheet.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_NAME}!A2:B").execute()
data = result.get('values', [])
item_prices = {row[0].strip().lower(): int(row[1]) for row in data}

# Helpers
def extract_core_pizza_name(pizza_text):
    patterns = [
        r'(margherita)',
        r'(farmhouse)',
        r'(mexicana)',
        r'(peppy paneer)',
        r'(veg extravaganza)',
    ]
    for pattern in patterns:
        match = re.search(pattern, pizza_text, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return pizza_text.strip().lower()

def parse_items(text):
    pattern = r'(\d+)\s+([\w\s]+?)(?:\sand\s|$)'
    matches = re.findall(pattern, text)
    return [(int(qty), name.strip()) for qty, name in matches]

def parse_toppings(text):
    topping_sets = {}
    patterns = re.findall(r'(.+?)\s+for\s+([\w\s]+?)(?:\sand\s|$)', text)
    for toppings, pizza in patterns:
        topping_list = [t.strip().lower() for t in re.split(r'and|,', toppings)]
        topping_sets[extract_core_pizza_name(pizza)] = topping_list
    return topping_sets

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Pizza Price Calculator API is running."})

@app.route('/calculate_price', methods=['POST'])
def calculate_price():
    request_json = request.get_json()
    if not request_json:
        return jsonify({'error': 'Invalid JSON'}), 400

    pizzaname = request_json.get('pizzaname', '')
    pizzatoppings = request_json.get('pizzatoppings', '')
    additionalitems = request_json.get('additionalitems', '')

    result_list = []

    parsed_pizzas = parse_items(pizzaname)
    parsed_toppings = parse_toppings(pizzatoppings)

    for qty, pizza_text in parsed_pizzas:
        core_pizza = extract_core_pizza_name(pizza_text)
        base_price = item_prices.get(core_pizza, 0)
        topping_total = 0

        toppings = parsed_toppings.get(core_pizza, [])
        for topping in toppings:
            topping_price = item_prices.get(topping, 0)
            topping_total += topping_price

        total_price_per_pizza = base_price + topping_total

        result_list.append({
            "name": pizza_text,
            "currency": "USD",
            "amount": total_price_per_pizza,
            "qty": qty
        })

    parsed_additional = parse_items(additionalitems)
    for qty, item in parsed_additional:
        item_price = item_prices.get(item.lower(), 0)
        result_list.append({
            "name": item,
            "currency": "USD",
            "amount": item_price,
            "qty": qty
        })

    return jsonify(result_list)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
