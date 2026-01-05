
import re
import httpx
from mcp.server.fastmcp import FastMCP  # official MCP SDK
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
    Return a prompt that instructs the AI agent to read the PDF and extract 'You bought' rows.
    """
    prompt = (
        "find and read the sharetransactions.pdf file .\n"
        "Locate the 'Activity' table.\n"
        "Extract only rows where Activity = 'You bought'.\n"
        "Return a CSV named 'transactions' with columns:\n"
        "- 'Country Name and Code' (static): 2.United State of America\n"
        "- 'ZIP Code' (static): 11111\n"
        "- 'Date of acquiring the interest' (YYYY-MM-DD) = Entry Date in PDF\n"
        "- 'Initial value of the investment' (numeric, INR) = Book Value (USD) convert to INR via tool 'usd_to_inr_on_date' for the respective date\n"
        "- 'units' (numeric) =  Number of Unit in pdf - its a number so don't convert \n"
        "- 'unit_price' (numeric, INR) = Unit Label Price (USD) convert to INR via tool 'usd_to_inr_on_date' for the respective date\n"
        "For the same date, if there are Employer and Employee transactions, "
        "sum book_value and units, and average unit_price into a single row.\n"
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
    server.run(transport="streamable-http")
