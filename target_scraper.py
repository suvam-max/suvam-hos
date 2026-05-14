import requests
import json
import csv
import time
import re
import os

# Final version of the target scraper script
# Includes credit monitoring and broad search logic (mobiles + direct lines)
# Uses environment variables for API key and enforces rate limiting.

SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
SERPER_URL = "https://google.serper.dev/search"

# Target Point of Contact roles
ROLES = [
    "Head of Physiotherapy",
    "SCM Head",
    "Procurement Head",
    "Medical Superintendent",
    "Purchase Manager",
    "Chief Procurement Officer",
    "Rehabilitation Head"
]

CREDIT_LIMIT = 125 # Stop at 5% of 2500 credits

def search_serper(query):
    if not SERPER_API_KEY:
        print("Error: SERPER_API_KEY not found in environment variables.")
        return "ERROR"

    payload = json.dumps({"q": query})
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    try:
        response = requests.request("POST", SERPER_URL, headers=headers, data=payload)
        if response.status_code == 403:
            return "OUT_OF_CREDITS"
        return response.json()
    except Exception:
        return None

def extract_numbers(text):
    # Matches Indian mobile numbers (10 digits starting 6-9) and landlines with extensions
    mobile_pattern = r'(?:(?:\+91|0)[- ]?)?[6-9]\d{4}[- ]?\d{5}|(?:(?:\+91|0)[- ]?)?[6-9]\d{2}[- ]?\d{3}[- ]?\d{4}|[6-9]\d{9}'
    landline_pattern = r'(?:0\d{2,4}[- ]?)?\d{6,8}(?:\s*(?:ext|extension|extn|x)\s*[:.\s]*\d{1,5})?'

    mobiles = re.findall(mobile_pattern, text)
    landlines = re.findall(landline_pattern, text)

    cleaned = []
    for m in mobiles:
        digits = re.sub(r'\D', '', m)
        if len(digits) == 10: cleaned.append(digits)
        elif len(digits) == 11 and digits.startswith('0'): cleaned.append(digits[1:])
        elif len(digits) == 12 and digits.startswith('91'): cleaned.append(digits[2:])

    for l in landlines:
        if any(keyword in l.lower() for keyword in ['ext', 'extension', 'x']):
            cleaned.append(l.strip())
        elif len(re.sub(r'\D', '', l)) >= 8:
            cleaned.append(l.strip())

    return list(set(cleaned))

def extract_email(text):
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    matches = re.findall(pattern, text)
    # Basic validation to avoid obvious junk emails
    valid = []
    junk_domains = ['sreenidhi.edu.in', 'sbi.co.in', 'gmail.com.co', 'test.com']
    for email in matches:
        if not any(domain in email.lower() for domain in junk_domains):
            valid.append(email)
    return list(set(valid))

def get_poc_name(hospital, role, counter):
    if counter <= CREDIT_LIMIT: return None, counter

    query = f'"{role}" "{hospital}" site:linkedin.com/in/ OR "{hospital}" "{role}" contact'
    results = search_serper(query)
    counter -= 1

    if results == "OUT_OF_CREDITS": return "STOP", counter
    if results == "ERROR": return "STOP", counter
    if not results or 'organic' not in results: return None, counter

    for result in results['organic'][:5]:
        title = result.get('title', '')
        snippet = result.get('snippet', '')

        if "linkedin.com/in/" in result.get('link', ''):
            name_part = title.split(' - ')[0].split(' | ')[0].split(' : ')[0].strip()
            # Name should be 2-4 words and not contain the hospital name
            if 2 <= len(name_part.split()) <= 4 and hospital.split()[0].lower() not in name_part.lower():
                clean_name = re.sub(r'^(Dr\.|Mr\.|Ms\.|Mrs\.|Dr |Mr |Ms |Mrs )\s*', '', name_part, flags=re.IGNORECASE)
                return clean_name, counter

        patterns = [
            r'([A-Z][a-z]+ [A-Z][a-z]+(?: [A-Z][a-z]+)?)\s+(?:is|serves as|works as|joined as)?\s+(?:the|a)?\s*' + re.escape(role),
            re.escape(role) + r' at ' + re.escape(hospital) + r' is ([A-Z][a-z]+ [A-Z][a-z]+(?: [A-Z][a-z]+)?)',
            re.escape(role) + r'\s+([A-Z][a-z]+ [A-Z][a-z]+(?: [A-Z][a-z]+)?)'
        ]

        for p in patterns:
            match = re.search(p, snippet, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if hospital.split()[0].lower() not in name.lower() and len(name.split()) >= 2:
                    return name, counter

    return None, counter

def find_contact_info(name, hospital, role, counter):
    if counter <= CREDIT_LIMIT: return [], [], counter

    if name: query = f'"{name}" "{hospital}" (mobile OR whatsapp OR phone OR email OR contact)'
    else: query = f'"{hospital}" "{role}" (direct line OR desk OR extension OR contact number)'

    results = search_serper(query)
    counter -= 1

    if results == "OUT_OF_CREDITS": return "STOP", [], counter
    if results == "ERROR": return "STOP", [], counter
    numbers = []
    emails = []
    if results and 'organic' in results:
        for result in results['organic']:
            text = result.get('snippet', '') + " " + result.get('title', '')
            numbers.extend(extract_numbers(text))
            emails.extend(extract_email(text))

    return list(set(numbers)), list(set(emails)), counter

def save_results(results, filename='poc_contacts.csv'):
    keys = ["Hospital Name", "City", "POC Name", "Designation", "Direct Mobile/Extension", "Email ID"]
    seen = set()
    unique_results = []
    for r in results:
        identifier = (r['Hospital Name'], r['POC Name'], r['Direct Mobile/Extension'])
        if identifier not in seen:
            unique_results.append(r)
            seen.add(identifier)

    with open(filename, 'w', newline='', encoding='utf-8') as output_file:
        dict_writer = csv.DictWriter(output_file, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(unique_results)
