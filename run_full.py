import csv
import time
import os
import target_scraper as scraper
from targets import TARGET_INSTITUTIONS

# Ensure 4-second delay and handle API key from env
ESTIMATED_CREDITS_LEFT = 2500

def main():
    if not os.environ.get("SERPER_API_KEY"):
        print("Please set SERPER_API_KEY environment variable.")
        return

    all_results = []
    if os.path.exists('poc_contacts.csv'):
        try:
            with open('poc_contacts.csv', 'r', newline='', encoding='utf-8') as f:
                all_results = list(csv.DictReader(f))
        except Exception:
            pass

    processed_hospitals = set([r['Hospital Name'] for r in all_results])
    cities = ["Bangalore", "Delhi", "Chennai", "Coimbatore", "Mumbai", "Ahmedabad", "Gurgaon"]
    counter = ESTIMATED_CREDITS_LEFT

    for city in cities:
        hospitals = TARGET_INSTITUTIONS.get(city, [])
        for hospital in hospitals:
            if hospital in processed_hospitals: continue
            print(f"\n=== Hospital: {hospital} ({city}) ===", flush=True)
            hospital_found_count = 0
            for role in scraper.ROLES:
                if counter <= scraper.CREDIT_LIMIT:
                    scraper.save_results(all_results)
                    return

                name, counter = scraper.get_poc_name(hospital, role, counter)
                if name == "STOP":
                    scraper.save_results(all_results)
                    return

                time.sleep(4) # USER CONSTRAINT: 4s delay

                numbers, emails, counter = scraper.find_contact_info(name, hospital, role, counter)
                if numbers == "STOP":
                    scraper.save_results(all_results)
                    return

                if numbers:
                    for num in numbers[:2]:
                        poc_name = name if name else f"{role} Department"
                        all_results.append({
                            "Hospital Name": hospital,
                            "City": city,
                            "POC Name": poc_name,
                            "Designation": role,
                            "Direct Mobile/Extension": num,
                            "Email ID": emails[0] if emails else ""
                        })
                        hospital_found_count += 1
                        print(f"  SUCCESS: {poc_name} - {num}", flush=True)

                time.sleep(4) # USER CONSTRAINT: 4s delay

            if hospital_found_count > 0:
                scraper.save_results(all_results)
            processed_hospitals.add(hospital)

    scraper.save_results(all_results)

if __name__ == "__main__":
    main()
