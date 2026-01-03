import io
import base64
import pdfplumber
from fastmcp import FastMCP

server = FastMCP("FA Tax Schedule MCP Server")

@server.tool()
def parse_pdf(file_bytes: bytes = None, file_base64: str = None) -> dict:
    """
    Extract 'You bought' transactions from the Activity table in the PDF.
    Accepts either raw PDF bytes or a base64-encoded string.
    Returns a list of transactions with entry_date, book_value, units, and unit_price.
    """
    transactions = []

    try:
        # Decide input source
        if file_bytes:
            pdf_stream = io.BytesIO(file_bytes)
        elif file_base64:
            pdf_stream = io.BytesIO(base64.b64decode(file_base64))
        else:
            return {"error": "No PDF data provided. Please upload file bytes or base64 string."}

        # Parse PDF
        with pdfplumber.open(pdf_stream) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 7:
                            continue
                        entry_date, activity, _, _, units, unit_price, book_value = row[:7]

                        # Only consider "You bought" rows
                        if activity and "You bought" in activity:
                            try:
                                transactions.append({
                                    "entry_date": entry_date,
                                    "book_value": float(book_value.replace("$", "").replace(",", "")) if book_value else None,
                                    "units": float(units) if units else None,
                                    "unit_price": float(unit_price.replace("$", "").replace(",", "")) if unit_price else None,
                                    "currency": "USD"
                                })
                            except Exception:
                                continue
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
