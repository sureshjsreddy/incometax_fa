import io, base64, pdfplumber
from fastmcp import FastMCP
from datetime import datetime

server = FastMCP("FA Tax Schedule MCP Server")

def normalize_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str.strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
    except Exception:
        return date_str

@server.tool()
def parse_pdf(file_bytes: bytes = None, file_base64: str = None) -> dict:
    """
    Extract 'You bought' transactions from the Activity table in the PDF.
    Accepts either raw PDF bytes or a base64-encoded string.
    """
    transactions = []

    try:
        # Decide input source
        if file_bytes:
            pdf_stream = io.BytesIO(file_bytes)
        elif file_base64:
            pdf_stream = io.BytesIO(base64.b64decode(file_base64))
        else:
            return {"error": "No PDF data provided."}

        with pdfplumber.open(pdf_stream) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 7:
                            continue
                        entry_date, activity, _, _, units, unit_price, book_value = row[:7]

                        if activity and "you bought" in activity.lower():
                            try:
                                transactions.append({
                                    "entry_date": normalize_date(entry_date.strip()),
                                    "book_value": float(str(book_value).replace("$", "").replace(",", "")) if book_value else None,
                                    "units": float(str(units).replace(",", "")) if units else None,
                                    "unit_price": float(str(unit_price).replace("$", "").replace(",", "")) if unit_price else None,
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
