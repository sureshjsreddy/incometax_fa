from fastmcp import FastMCP

server = FastMCP("FA Tax Schedule MCP Server")

@server.tool()
def parse_pdf(file_path: str):
    transactions = [
        {"date": "2025-01-01", "shares": 100, "fmv": 50.0, "country": "US"},
        {"date": "2025-02-15", "shares": 200, "fmv": 55.0, "country": "US"},
    ]
    return {"transactions": transactions}

@server.tool()
def generate_tax_schedule(transactions: list):
    schedule = {
        "opening_balance": 0,
        "additions": sum(t["shares"] for t in transactions),
        "closing_balance": sum(t["shares"] for t in transactions),
        "country": transactions[0]["country"] if transactions else "Unknown",
    }
    return {"foreign_asset_schedule": schedule}

if __name__ == "__main__":
    # Explicitly run with HTTP transport for cloud hosting
    server.run(transport="http", host="0.0.0.0", port=8000)
