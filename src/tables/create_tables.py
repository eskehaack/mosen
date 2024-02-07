def table_defs():
    return {
        "users": """
            CREATE TABLE users (
                barcode varchar(255),
                name varchar(255),
                rank varchar(255),
                team varchar(255)
            )
        """,
        "prods": """
            CREATE TABLE prods (
                barcode varchar(255),
                name varchar(255),
                price varchar(255),
                category varchar(255),
                current_stock varchar(255),
                initial_stock varchar(255)
            )
        """,
        "transactions": """
            CREATE TABLE transactions (
                barcode_user varchar(255),
                barcode_prod varchar(255),
                price varchar(255),
                timestamp varchar(255)
            )
        """,
        "temporary": """
            CREATE TABLE temporary (
                barcode_prod varchar(255),
                name varchar(255)
            )
            """,
    }
