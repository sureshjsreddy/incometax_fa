
import re
import httpx
import io, base64, pdfplumber
from fastmcp import FastMCP
from datetime import datetime

server = FastMCP("FA Tax Schedule Server", json_response=True)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

@server.tool()
async def usd_to_inr_on_date(date: str, amount: float = 1.0) -> dict:
    """
    Get the USD→INR exchange rate for a given YYYY-MM-DD date.
    Optionally convert an amount (default 1.0 USD).
    Returns: {date, base, target, rate, amount_in_target}
    """
    if not DATE_RE.match(date):
        raise ValueError("`date` must be YYYY-MM-DD")
    if amount <= 0:
        raise ValueError("`amount` must be > 0")

    # Frankfurter historical endpoint: /v1/{date}?base=USD&symbols=INR
    url = f"https://api.frankfurter.dev/v1/{date}"
    params = {"base": "USD", "symbols": "INR"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    rate = data.get("rates", {}).get("INR")
    if rate is None:
        raise RuntimeError("INR rate not available for the requested date")

    # Frankfurter returns the effective FX date (UTC)
    effective_date = data.get("date", date)

    return {
        "date": effective_date,
        "base": "USD",
        "target": "INR",
        "rate": rate,
        "amount_in_target": round(amount * rate, 6),
    }

@server.tool()
def get_fa_transactions() -> dict:
    """
    Return a prompt that instructs the AI agent to read the PDF and extract 'You bought' or 'Opening Value' or 'Opening balance' rows '.
    """
    prompt = (
        "find and read the sharetransactions.pdf file .\n"
        "Locate the 'Activity' table.\n"
        "Extract only rows where Activity = 'You bought' or 'Opening Value' or 'Opening balance'.\n"
        "Create  a CSV file named 'transactions' with columns:\n"
        "- 'Country Name and Code' (static): 2-UNITED STATES OF AMERICA\n"
        "- 'Name of entity' (static): CGI Inc\n"
        "- 'Address of entity' (static): 1350 RENELEVES QUE BOULEVAR D WEST- 5TH FLOOR- MONTREAL\n"
        "- 'ZIP Code' (static): H3G 1T4\n"
        "- 'Nature of entity' (static): Private Limited\n"
        "- 'Date of acquiring the interest' (YYYY-MM-DD) = Entry Date in PDF\n"
        "- 'Initial value of the investment' (numeric, INR) = Book Value (USD) convert to INR via tool 'usd_to_inr_on_date' for the respective date\n"
        "- 'Peak value of the investment' (numeric, INR) = Max unit price form final list of all __unit_price of latest year and multiply with units for the respective date"
        "- 'Closing balance' (numeric, INR) = see instructions for 'Closing balance'"
        "- '__units' (numeric) =  Number of Unit in pdf - its a number so don't convert \n"
        "- '__unit_price' (numeric, INR) = Unit Label Price (USD) convert to INR via tool 'usd_to_inr_on_date' for the respective date\n"
        "For the same date, if there are Employer and Employee transactions, "
        "sum the  book_value, __units, Peak value of the investment and average the __unit_price into a single row.\n"
        "finally sort rows by [Date of acquiring the interest]\n"
        "example: 'Peak value of the investment' column value is MAX price from list of all __unit_price of latest year(ignore previous year dates) multply with no of units of current row date\n"
        "##instructions for 'Closing balance'## -  "Locate the 'Activity' table. find the row where Activity = 'Closing balance'.\n"  
        "and from above row get the  Unit Label Price (USD) convert to INR via tool 'usd_to_inr_on_date' for the respective date as closingINRPrice\n"
        "now multiply the closingINRPrice with value from '__units' column of respective row and update the value in 'Closing balance' column\n"
        
    )
    return {"next_prompt": prompt}

@server.tool()
def generate_tax_schedule(transactions: list) -> dict:
    """
    Generate a foreign asset schedule summary from transaction rows.
    Expects each item to have keys: date, units, unit_price, initial_value_in_inr (optional).
    """
    def _num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    total_units = sum(_num(t.get("units")) for t in transactions)
    # If you computed INR per row, prefer that; otherwise use units * unit_price
    total_inr = sum(_num(t.get("initial_value_in_inr", _num(t.get("units")) * _num(t.get("unit_price"))))
                    for t in transactions)

    schedule = {
        "opening_balance_units": 0.0,         # fill if you have prior period
        "additions_units": total_units,
        "closing_balance_units": total_units, # simplistic; adjust for disposals
        "total_value_in_inr": round(total_inr, 2),
        "currency": "INR",
    }
    return {"foreign_asset_schedule": schedule}
  
if __name__ == "__main__":
    server.run(transport="http", host="0.0.0.0", port=8000)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
