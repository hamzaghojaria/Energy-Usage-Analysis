from fastapi import FastAPI, UploadFile, File, HTTPException
import pandas as pd
import uvicorn
from datetime import datetime
from io import StringIO
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global DataFrame to store uploaded data
df = None
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    global df
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    try:
        content = await file.read()
        data_str = content.decode("utf-8")
        df = pd.read_csv(StringIO(data_str), skiprows=6)  # Adjust if needed

        # Remove spaces in column names
        df.columns = df.columns.str.strip()

        df["DATETIME"] = pd.to_datetime(df["DATE"] + " " + df["START TIME"], format="%Y-%m-%d %H:%M")
        df["USAGE (kWh)"] = df["USAGE (kWh)"].astype(float)
        df["COST"] = df["COST"].astype(str).str.replace("$", "", regex=False).astype(float)


        if df.empty:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        return {"message": "File uploaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


@app.get("/total_usage")
def total_usage(period: str = "week"):
    try:
        if df is None:
            raise HTTPException(status_code=400, detail="No data uploaded yet")

        if "DATETIME" not in df.columns:
            return {"error": "DATETIME column not found in uploaded file"}

        df["DATETIME"] = pd.to_datetime(df["DATETIME"], errors="coerce")

        if period == "day":
            result = df.groupby(df["DATETIME"].dt.date, as_index=False)["USAGE (kWh)"].sum()
            result.index = result.index.astype(str)  # Convert index to string
        elif period == "week":
            result = df.groupby(df["DATETIME"].dt.to_period("W"))["USAGE (kWh)"].sum()
            result.index = result.index.astype(str)  # Convert index to string
        elif period == "month":
            result = df.groupby(df["DATETIME"].dt.to_period("M"))["USAGE (kWh)"].sum()
            result.index = result.index.astype(str)  # Convert index to string
        else:
            raise HTTPException(status_code=400, detail="Invalid period. Use 'day', 'week', or 'month'.")
        return result.to_dict()  # Fix applied here
    except Exception as e:
        print("Error:", str(e))
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/cost_trends")
def cost_trends(period: str = "day"):
    print(period)
    if df is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet")

    if "DATETIME" not in df.columns:
        return {"error": "DATETIME column not found in uploaded file"}

    df["DATETIME"] = pd.to_datetime(df["DATETIME"], errors="coerce")

    if period == "day":
        result = df.groupby(df["DATETIME"].dt.date)["COST"].sum()
    elif period == "week":
        result = df.groupby(df["DATETIME"].dt.to_period("W"))["COST"].sum()
        result.index = result.index.astype(str)  # Convert index to string
    elif period == "month":
        result = df.groupby(df["DATETIME"].dt.to_period("M"))["COST"].sum()
        result.index = result.index.astype(str)  # Convert index to string
    else:
        raise HTTPException(status_code=400, detail="Invalid period. Use 'day', 'week', or 'month'.")

    return result.to_dict()

@app.get("/peak_hours")
def peak_hours():
    if df is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet")

    peak = df.groupby(df["DATETIME"].dt.hour)["USAGE (kWh)"].sum()
    peak_hour = int(peak.idxmax())
    return {"peak_hour": peak_hour, "usage": peak[peak_hour]}


@app.get("/anomalies")
def detect_anomalies():
    if df is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet")

    mean_usage = df["USAGE (kWh)"].mean()
    std_dev = df["USAGE (kWh)"].std()
    threshold = mean_usage + 2 * std_dev
    anomalies = df[df["USAGE (kWh)"] > threshold]
    anomalies["DATETIME"] = anomalies["DATETIME"].astype(str)

    return anomalies[["DATETIME", "USAGE (kWh)"]].to_dict()

@app.get("/hourly_usage_trend")
def hourly_usage_trend():
    if df is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet")

    trend = df.groupby(df["DATETIME"].dt.hour)["USAGE (kWh)"].mean()
    return trend.to_dict()

@app.get("/weekday_vs_weekend")
def weekday_vs_weekend():
    if df is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet")

    df["WEEKDAY"] = df["DATETIME"].dt.weekday
    weekday_usage = df[df["WEEKDAY"] < 5]["USAGE (kWh)"].sum()
    weekend_usage = df[df["WEEKDAY"] >= 5]["USAGE (kWh)"].sum()
    return {"weekday_usage": weekday_usage, "weekend_usage": weekend_usage}

@app.get("/high_cost_days")
def high_cost_days():
    if df is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet")

    cost_per_kwh = df.groupby(df["DATETIME"].dt.date)["COST"].sum() / df.groupby(df["DATETIME"].dt.date)["USAGE (kWh)"].sum()
    high_cost_days = cost_per_kwh[cost_per_kwh > cost_per_kwh.mean() + cost_per_kwh.std()].to_dict()
    return high_cost_days

@app.get("/forecast_usage")
def forecast_usage(days: int = 7):
    if df is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet")

    daily_usage = df.groupby(df["DATETIME"].dt.date)["USAGE (kWh)"].sum()
    moving_avg = daily_usage.rolling(window=7).mean().dropna()
    forecast = moving_avg[-days:].to_dict()
    return forecast

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
