import requests

API_URL = "http://127.0.0.1:8080"

# Eric's login credentials
login_data = {
    "username": "Eric",
    "password": "Eric@!99"
}

# Step 1: Log in and get token
login_response = requests.post(f"{API_URL}/login", json=login_data)
if login_response.status_code != 200:
    print("Login failed:", login_response.text)
    exit()

token = login_response.json()["access_token"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Example 1
approved_example = {
    "name": "Alice",
    "annual_income": 90000,
    "debt_to_income_ratio": 0.25,
    "credit_score": 750,
    "loan_amount": 20000,
    "interest_rate": 5.0,
    "gender": "Female",
    "marital_status": "Single",
    "education_level": "Bachelor",
    "employment_status": "Employed",
    "loan_purpose": "Home",
    "grade_subgrade": "A1"
}

# Example 2
rejected_example = {
    "name": "Bob",
    "annual_income": 30000,
    "debt_to_income_ratio": 0.6,
    "credit_score": 580,
    "loan_amount": 25000,
    "interest_rate": 7.5,
    "gender": "Male",
    "marital_status": "Single",
    "education_level": "High School",
    "employment_status": "Unemployed",
    "loan_purpose": "Car",
    "grade_subgrade": "E2"
}

def test_prediction(data):
    response = requests.post(f"{API_URL}/predict_single", json=data, headers=headers)
    if response.status_code == 200:
        result = response.json()
        approve_prob = result['probability'] * 100
        reject_prob = (1 - result['probability']) * 100

        prediction_label = "APPROVED" if result['prediction'] == 1 else "REJECTED"

        print(f"Name: {data['name']}")
        print(f"Prediction: {prediction_label}")
        print(f"Probability Approve: {approve_prob:.2f}%")
        print(f"Probability Reject: {reject_prob:.2f}%")
        print("-"*40)
    else:
        print(f"Failed for {data['name']}: {response.text}")

if __name__ == "__main__":
    test_prediction(approved_example)
    test_prediction(rejected_example)
