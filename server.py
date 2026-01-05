import io, base64, pdfplumber
import re
import httpx

from fastmcp import FastMCP
from datetime import datetime

server = FastMCP("FA Tax Schedule Server")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

@server.tool()
async def usd_to_inr_on_date(date: str, amount: float = 1.0) -> dict:
    """
    Get the USD→INR exchange rate for a given YYYY-MM-DD date.
    Optionally convert an amount (default 1.0 USD).
    Returns: {date, base, target, rate, amount_in_target}
    """
    if not DATE_RE.match(date):
        raise ValueError("date must be YYYY-MM-DD")
    if amount <= 0:
        raise ValueError("amount must be > 0")

    # Frankfurter historical endpoint: /v1/{date}?base=USD&symbols=INR
    url = f"https://api.frankfurter.dev/v1/{date}"
    params = {"base": "USD", "symbols": "INR"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    rate = data["rates"].get("INR")
    if rate is None:
        raise RuntimeError("INR rate not available for the requested date")

    # date returned is the effective FX date per Frankfurter (UTC)
    effective_date = data.get("date", date)

    return {
        "date": effective_date,
        "base": "USD",
        "target": "INR",
        "rate": rate,
        "amount_in_target": round(amount * rate, 6)
    }

@server.tool()
def get_fa_transactions() -> dict:
    """
    Return a prompt that instructs the AI agent to read the PDF and extract 'You bought' rows.
    """
    prompt = (
        "Read the attached shartransactions PDF. "
        "Locate the 'Activity' table. "
        "Extract only rows where Activity = 'You bought'. "
        "For each row, return a csv row  with:\n"
        "- column:'Date of acquiring the interest' (normalize to YYYY-MM-DD) - Entry Date coumn in pdf\n"
        "- column:'Initial value of the investment' (numeric, INR) - Book Value in pdf is in USD convert to INR \n"
        "- column: 'units' (numeric)\n"
        "- column: 'unit_price' (numeric, INR ) Unit Label Price in pdf is in USD convert to INR \n"
        "Output as a csv file called 'transactions'."
        "for same date if there is Employer and Employee transactions then sum up book_value,units, and average the unit_price in to single row"
    )

    return {"next_prompt": prompt}

@server.tool()
def generate_tax_schedule(transactions: list) -> dict:
    """
    Generate a foreign asset schedule for income tax filing.
    """
    schedule = {
        "opening_balance": 0,
        "additions": sum(t["units"] for t in transactions if t["units"]),
        "closing_balance": sum(t["units"] for t in transactions if t["units"]),
        "currency": "USD",
    }
    return {"foreign_asset_schedule": schedule}

if __name__ == "__main__":
    server.run(transport="http", host="0.0.0.0", port=8000)
