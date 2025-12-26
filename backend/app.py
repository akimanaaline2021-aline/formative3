import joblib
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import jwt
import uuid
from typing import List

import database as db

# JWT settings
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Load ML pipeline
pipeline = joblib.load("../best_pipeline.pkl")
meta = joblib.load("../pipeline_meta.pkl")

app = FastAPI(title="Loan Payback Prediction API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

security = HTTPBearer()

# Pydantic models
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class LoanData(BaseModel):
    name: str
    annual_income: float
    debt_to_income_ratio: float
    credit_score: float
    loan_amount: float
    interest_rate: float
    gender: str
    marital_status: str
    education_level: str
    employment_status: str
    loan_purpose: str
    grade_subgrade: str

class PredictionResponse(BaseModel):
    id: int
    prediction: int
    probability: float
    created_at: str

# JWT functions
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_token(token)
    username = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.get_user_by_username(username)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# Auth endpoints
@app.post("/register", response_model=Token)
def register(user_data: UserRegister):
    # Check if user exists
    if db.get_user_by_username(user_data.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    if db.get_user_by_email(user_data.email):
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create user
    user = db.create_user(user_data.username, user_data.email, user_data.password)
    
    # Create token
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=Token)
def login(user_data: UserLogin):
    user = db.get_user_by_username(user_data.username)
    if not user or not db.verify_password(user_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

# Prediction endpoints
@app.post("/predict_single", response_model=PredictionResponse)
def predict_single(data: LoanData, current_user: dict = Depends(get_current_user)):
    # Make prediction (exclude name from model input)
    loan_data_dict = data.dict()
    name = loan_data_dict.pop("name")
    
    df = pd.DataFrame([loan_data_dict], columns=meta["all_feature_columns"])
    pred = pipeline.predict(df)[0]
    prob = pipeline.predict_proba(df)[0, 1]
    
    # Add name back for storage
    loan_data_dict["name"] = name
    
    # Save to database
    prediction = db.create_prediction(
        user_id=current_user["id"],
        loan_data=loan_data_dict,
        prediction=int(pred),
        probability=float(prob),
        prediction_type="single"
    )
    
    return {
        "id": prediction["id"],
        "prediction": prediction["prediction"],
        "probability": prediction["probability"],
        "created_at": prediction["created_at"]
    }

@app.post("/predict_batch")
async def predict_batch(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    df = pd.read_csv(file.file)
    
    # Extract names before prediction
    names = df["name"].tolist() if "name" in df.columns else ["Unknown"] * len(df)
    
    # Remove name column for prediction
    df_for_prediction = df.drop(columns=["name"], errors="ignore")
    
    preds = pipeline.predict(df_for_prediction)
    probs = pipeline.predict_proba(df_for_prediction)[:, 1]
    
    # Generate batch ID
    batch_id = str(uuid.uuid4())
    
    # Save all predictions
    predictions = []
    for idx, row in df_for_prediction.iterrows():
        loan_data = {
            "name": names[idx],
            "annual_income": float(row["annual_income"]),
            "debt_to_income_ratio": float(row["debt_to_income_ratio"]),
            "credit_score": float(row["credit_score"]),
            "loan_amount": float(row["loan_amount"]),
            "interest_rate": float(row["interest_rate"]),
            "gender": str(row["gender"]),
            "marital_status": str(row["marital_status"]),
            "education_level": str(row["education_level"]),
            "employment_status": str(row["employment_status"]),
            "loan_purpose": str(row["loan_purpose"]),
            "grade_subgrade": str(row["grade_subgrade"])
        }
        
        prediction = db.create_prediction(
            user_id=current_user["id"],
            loan_data=loan_data,
            prediction=int(preds[idx]),
            probability=float(probs[idx]),
            prediction_type="batch",
            batch_id=batch_id
        )
        
        predictions.append({
            "name": names[idx],
            "prediction": int(preds[idx]),
            "probability": float(probs[idx])
        })
    
    return {"batch_id": batch_id, "count": len(predictions), "predictions": predictions}

@app.get("/predictions/history")
def get_history(current_user: dict = Depends(get_current_user)):
    predictions = db.get_user_predictions(current_user["id"])
    return predictions

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8080, reload=True)