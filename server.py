import io, base64, pdfplumber
from fastmcp import FastMCP
from datetime import datetime

server = FastMCP("FA Tax Schedule Server")

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
        "- entry_date (normalize to YYYY-MM-DD)\n"
        "- book_value (numeric, USD)\n"
        "- units (numeric)\n"
        "- unit_price (numeric, USD)\n\n"
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
