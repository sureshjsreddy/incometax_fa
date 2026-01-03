import pdfplumber
from fastmcp import FastMCP

server = FastMCP("FA Tax Schedule MCP Server")

@server.tool()
def parse_pdf(file_path: str) -> dict:
    """
    Extract 'You bought' transactions from the Activity table in the PDF.
    Returns a list of transactions with entry_date, book_value, units, and unit_price.
    """
    transactions = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    # Skip header rows, iterate over data rows
                    for row in table:
                        if not row or len(row) < 7:
                            continue
                        entry_date = row[0]
                        activity = row[1]
                        type_of_money = row[2]
                        cash = row[3]
                        units = row[4]
                        unit_price = row[5]
                        book_value = row[6]

                        # Only consider "You bought" rows
                        if activity and "You bought" in activity:
                            try:
                                transactions.append({
                                    "entry_date": entry_date,
                                    "book_value": float(book_value.replace("$", "").replace(",", "")) if book_value else None,
                                    "units": float(units) if units else None,
                                    "unit_price": float(unit_price.replace("$", "").replace(",", "")) if unit_price else None,
                                    "currency": "USD",
                                    "source": type_of_money
                                })
                            except Exception:
                                # Skip rows with parsing issues
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
