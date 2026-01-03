import io
import pdfplumber
from fastmcp import FastMCP

server = FastMCP("FA Tax Schedule MCP Server")

@server.tool()
def parse_pdf(file_bytes: bytes) -> dict:
    """
    Extract 'You bought' transactions from the Activity table in the PDF.
    Accepts raw PDF bytes instead of a file path.
    """
    transactions = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for row in tables:
                    if not row or len(row) < 7:
                        continue
                    entry_date, activity, _, _, units, unit_price, book_value = row[:7]
                    if activity and "You bought" in activity:
                        transactions.append({
                            "entry_date": entry_date,
                            "book_value": float(book_value.replace("$", "").replace(",", "")) if book_value else None,
                            "units": float(units) if units else None,
                            "unit_price": float(unit_price.replace("$", "").replace(",", "")) if unit_price else None,
                            "currency": "USD"
                        })
    except Exception as e:
        return {"error": str(e)}

    return {"transactions": transactions}


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
