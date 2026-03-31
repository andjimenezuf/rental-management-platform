from MARIADB_CREDS import DB_CONFIG
from mariadb import connect
from models.RentalHistory import RentalHistory
from models.Waitlist import Waitlist
from models.Item import Item
from models.Rental import Rental
from models.Customer import Customer
from datetime import date, timedelta

EXTENSION_DAYS = 14


conn = connect(user=DB_CONFIG["username"], password=DB_CONFIG["password"], host=DB_CONFIG["host"],
               database=DB_CONFIG["database"], port=DB_CONFIG["port"])


cur = conn.cursor()


def add_item(new_item: Item = None):
    """
    new_item - An Item object containing a new item to be inserted into the DB in the item table.
        new_item and its attributes will never be None.
    """

    insert_item_query = """
        INSERT INTO item 
        (i_item_sk, i_item_id, i_rec_start_date, i_product_name, i_brand, i_class, i_category, i_manufact, i_current_price, i_num_owned)
        VALUES 
        ((SELECT COALESCE(MAX(i_item_sk), 0) + 1 FROM item AS tmp), ?, ?, ?, ?, NULL, ?, ?, ?, ?)
        """
    
    cur.execute(insert_item_query,( new_item.item_id,f"{new_item.start_year}-01-01",new_item.product_name,new_item.brand, 
                                   new_item.category, new_item.manufact, new_item.current_price, new_item.num_owned,),)


def add_customer(new_customer: Customer = None):
    """
    new_customer - A Customer object containing a new customer to be inserted into the DB in the customer table.
        new_customer and its attributes will never be None.
    """
    name_parts = new_customer.name.split()
    first_name = name_parts[0]
    last_name = name_parts[1]

    address_parts = new_customer.address.split(",")
    street_parts = address_parts[0].split()
    state_zip_parts = address_parts[-1].split()

    street_num = street_parts[0]
    street_name = " ".join(street_parts[1:])
    city = address_parts[1].strip()
    state = state_zip_parts[0].strip()
    zip_code = state_zip_parts[1]


    insert_customer_address_query = """
    INSERT INTO customer_address
    (ca_address_sk, ca_street_number, ca_street_name, ca_city, ca_state, ca_zip)
    VALUES 
    ((SELECT COALESCE(MAX(ca_address_sk), 0) + 1 FROM customer_address AS tmp), ?,?,?,?,?)
    """
    cur.execute(insert_customer_address_query, (street_num, street_name, city, state, zip_code))

    insert_customer_query = """
    INSERT into customer 
    (c_customer_sk, c_customer_id, c_first_name, c_last_name, c_email_address, c_current_addr_sk)
    VALUES 
    ((SELECT COALESCE(MAX(c_customer_sk), 0) + 1 FROM customer AS tmp), 
    ?,?,?,?,
    (SELECT MAX(ca_address_sk) FROM customer_address))
    """
    cur.execute(insert_customer_query, (new_customer.customer_id, first_name, last_name, new_customer.email))


def edit_customer(original_customer_id: str = None, new_customer: Customer = None):
    """
    original_customer_id - A string containing the customer id for the customer to be edited.
    new_customer - A Customer object containing attributes to update. If an attribute is None, it should not be altered.
    """
    # get null attributes from new_customer
    # Update cosumer with none null attributes
    cur.execute("SELECT c_current_addr_sk FROM customer WHERE c_customer_id = ?", (original_customer_id,))
    c_current_addr_sk = cur.fetchone()[0]
    set_clauses = []
    params = []

    if new_customer.customer_id is not None:
        set_clauses.append("c_customer_id = ?")
        params.append(new_customer.customer_id)

    if new_customer.email is not None:
        set_clauses.append("c_email_address = ?")
        params.append(new_customer.email)

    if new_customer.name is not None:
        name_parts = new_customer.name.split()
        first_name = name_parts[0]
        last_name = name_parts[1]

        set_clauses.append("c_first_name = ?")
        params.append(first_name)

        set_clauses.append("c_last_name = ?")
        params.append(last_name)

    if set_clauses:
        set_clause_sql = ", ".join(set_clauses)

    query = f"""
    UPDATE customer
    SET {set_clause_sql}
    WHERE c_customer_id = ?;
    """

    params.append(original_customer_id)
    cur.execute(query, tuple(params))    

    set_clauses = []
    params = []
    if new_customer.address is not None:
        address_parts = new_customer.address.split(",")
        street_parts = address_parts[0].split()
        state_zip_parts = address_parts[-1].split()

        street_num = street_parts[0]
        street_name = " ".join(street_parts[1:])
        city = address_parts[1].strip()
        state = state_zip_parts[0].strip()
        zip_code = state_zip_parts[1]

        set_clauses.append("ca_street_number = ?")
        set_clauses.append("ca_street_name = ?")
        set_clauses.append("ca_city = ?")
        set_clauses.append("ca_state = ?")
        set_clauses.append("ca_zip = ?")
        params.append(street_num)
        params.append(street_name)
        params.append(city)
        params.append(state)
        params.append(zip_code)
    if set_clauses:
        set_clause_sql = ", ".join(set_clauses)
    params.append(c_current_addr_sk)
    
    query = f"""
    UPDATE customer_address
    SET {set_clause_sql}
    WHERE ca_address_sk = ?;
    """
    cur.execute(query, tuple(params))


def rent_item(item_id: str = None, customer_id: str = None):
   """
    item_id - A string containing the Item ID for the item being rented.
    customer_id - A string containing the customer id of the customer renting the item.
    """
   insert_new_rental_query = """
    INSERT INTO rental (item_id, customer_id, rental_date, due_date)
    VALUES (?, ?, ?, ?)
    """
   todays_date = date.today()
   due_date = todays_date + timedelta(days=14)

   cur.execute(insert_new_rental_query, (item_id, customer_id, todays_date, due_date))
   

def waitlist_customer(item_id: str = None, customer_id: str = None) -> int:
    """
    Returns the customer's new place in line.
    """
    waitlist_position = line_length(item_id) + 1
    insert_waitlist_query = """
    INSERT INTO waitlist (item_id, customer_id, place_in_line)
    VALUES (?,?,?)
    """
    cur.execute(insert_waitlist_query, (item_id, customer_id, waitlist_position))
    return waitlist_position


def update_waitlist(item_id: str = None):
    """
    Removes person at position 1 and shifts everyone else down by 1.
    """
    delete_front_waitlist_query = """
    DELETE FROM waitlist
    WHERE item_id = ? and place_in_line = 1
    """
    cur.execute(delete_front_waitlist_query, (item_id,))

    update_remaining_positions_query = """
    UPDATE waitlist
    SET place_in_line = place_in_line - 1
    WHERE item_id = ? AND place_in_line >1
    """
    cur.execute(update_remaining_positions_query, (item_id,))


def return_item(item_id: str = None, customer_id: str = None):
    """
    Moves a rental from rental to rental_history with return_date = today.
    """
    # Get rental_date and due_date
    get_customer_rental_dates_query = """
    SELECT rental_date, due_date
    FROM rental
    WHERE item_id = ? AND customer_id = ?
    """
    
    cur.execute(get_customer_rental_dates_query, (item_id, customer_id))
    customer_rental_dates = cur.fetchone()
    rental_date = customer_rental_dates[0]
    due_date = customer_rental_dates[1]
    if customer_rental_dates is None:
        return

    insert_rental_history_query = """
    INSERT INTO rental_history (item_id, customer_id, rental_date, due_date, return_date)
    VALUES (?,?,?,?,?)
    """
    return_date = date.today()
    cur.execute(insert_rental_history_query, (item_id, customer_id, rental_date, due_date,return_date))

    delete_past_rental_query = """
    DELETE FROM rental
    WHERE item_id = ? and customer_id = ?
    """
    cur.execute(delete_past_rental_query, (item_id, customer_id))
    

def grant_extension(item_id: str = None, customer_id: str = None):
    """
    Adds 14 days to the due_date.
    """
    select_due_date_query = """
    SELECT due_date
    FROM rental
    WHERE item_id = ? AND customer_id = ?
    """
    cur.execute(select_due_date_query, (item_id, customer_id))
    current_due_date = cur.fetchone()[0]
    new_due_date = current_due_date + timedelta(days=EXTENSION_DAYS)


    update_due_date_query = """
    UPDATE rental
    SET due_date = ?
    WHERE item_id = ? AND customer_id = ?
    """
    cur.execute(update_due_date_query, (new_due_date, item_id, customer_id))


def get_filtered_items(filter_attributes: Item = None,
                       use_patterns: bool = False,
                       min_price: float = -1,
                       max_price: float = -1,
                       min_start_year: int = -1,
                       max_start_year: int = -1) -> list[Item]:
    """
    Returns a list of Item objects matching the filters.
    """
    item_to_source_cols = {
        "item_id": "i_item_id",
        "product_name": "i_product_name",
        "brand": "i_brand",
        "category": "i_category",
        "manufact": "i_manufact",
        "current_price": "i_current_price",
        "start_year": "YEAR(i_rec_start_date)",
        "num_owned": "i_num_owned",
    }

    where_clauses = []
    params = []

    for attr, value in vars(filter_attributes).items():
        if value is not None and value != -1:
            column = item_to_source_cols[attr]

            if use_patterns and isinstance(value, str):
                where_clauses.append(f"{column} LIKE ?")
            else:
                where_clauses.append(f"{column} = ?")

            params.append(value)

    if min_price != -1:
        where_clauses.append("i_current_price >= ?")
        params.append(min_price)

    if max_price != -1:
        where_clauses.append("i_current_price <= ?")
        params.append(max_price)

    if min_start_year != -1:
        where_clauses.append("YEAR(i_rec_start_date) >= ?")
        params.append(min_start_year)

    if max_start_year != -1:
        where_clauses.append("YEAR(i_rec_start_date) <= ?")
        params.append(max_start_year)

    select_filtered_items_query = """
    SELECT
        i_item_id,
        i_product_name,
        i_brand,
        i_category,
        i_manufact,
        i_current_price,
        YEAR(i_rec_start_date),
        i_num_owned
    FROM item
    """

    if where_clauses:
        where_clause_sql = " AND ".join(where_clauses)
        select_filtered_items_query += f" WHERE {where_clause_sql}"

    cur.execute(select_filtered_items_query, tuple(params))
    filtered_rows = cur.fetchall()

    results = []
    for row in filtered_rows:
        results.append(
            Item(
                item_id=row[0].strip() if row[0] is not None else None,
                product_name=row[1].strip() if row[1] is not None else None,
                brand=row[2].strip() if row[2] is not None else None,
                category=row[3].strip() if row[3] is not None else None,
                manufact=row[4].strip() if row[4] is not None else None,
                current_price=float(row[5]) if row[5] is not None else -1,
                start_year=row[6] if row[6] is not None else -1,
                num_owned=row[7] if row[7] is not None else -1,
            )
        )

    return results
    

def get_filtered_customers(filter_attributes: Customer = None, use_patterns: bool = False) -> list[Customer]:
    """
    Returns a list of Customer objects matching the filters.
    """
    # Collect non null/ -1 filter_attribute attributes
    customer_to_source_col = {
        "customer_id":"c_customer_id",
        "name" : "CONCAT(c_first_name, ' ', c_last_name)",
        "address" :  "",
        "email":"c_email_address"
    }

    where_clause = []
    params = []

    for attr, val in vars(filter_attributes).items():
        if val is not None:
            source_col = customer_to_source_col[attr]
            if use_patterns and isinstance(val, str):
                where_clause.append(f"{source_col} LIKE ?")
            else:
                where_clause.append(f"{source_col} = ?")
            params.append(val)
        
    
    where_clause_sql = ""
    if where_clause:
        where_clause_sql =  " AND ".join(where_clause)
    select_filtered_customers = f"""
    SELECT
        c.c_customer_id,
        c.c_first_name,
        c.c_last_name,
        ca.ca_street_number,
        ca.ca_street_name,
        ca.ca_city,
        ca.ca_state,
        ca.ca_zip,
        c.c_email_address
    FROM customer c
    JOIN customer_address ca
    ON c.c_current_addr_sk = ca.ca_address_sk
    WHERE {where_clause_sql}
    """
    cur.execute(select_filtered_customers, tuple(params))


    filtered_result = cur.fetchall()
    result = []
    for row in filtered_result:
        address = ",".join(row[2:-1])
        name = " ".join(row[2:4])
        result.append(
            Customer(customer_id=row[1] if row[1] is not None else None,
                     name= name if name is not None else None,
                     address=row[2] if address is not None else None,
                     email=row[4] if row[4] is not None else None,
                     )
        )

    return result
        
        
        

        



def get_filtered_rentals(filter_attributes: Rental = None,
                         min_rental_date: str = None,
                         max_rental_date: str = None,
                         min_due_date: str = None,
                         max_due_date: str = None) -> list[Rental]:
    """
    Returns a list of Rental objects matching the filters.
    """
    raise NotImplementedError("you must implement this function")


def get_filtered_rental_histories(filter_attributes: RentalHistory = None,
                                  min_rental_date: str = None,
                                  max_rental_date: str = None,
                                  min_due_date: str = None,
                                  max_due_date: str = None,
                                  min_return_date: str = None,
                                  max_return_date: str = None) -> list[RentalHistory]:
    """
    Returns a list of RentalHistory objects matching the filters.
    """
    raise NotImplementedError("you must implement this function")


def get_filtered_waitlist(filter_attributes: Waitlist = None,
                          min_place_in_line: int = -1,
                          max_place_in_line: int = -1) -> list[Waitlist]:
    """
    Returns a list of Waitlist objects matching the filters.
    """
    raise NotImplementedError("you must implement this function")


def number_in_stock(item_id: str = None) -> int:
    """
    Returns num_owned - active rentals. Returns -1 if item doesn't exist.
    """

    item_query = """
    SELECT i_num_owned
    FROM item
    WHERE i_item_id = ?;
    """

    cur.execute(item_query, (item_id,))
    num_owned_row = cur.fetchone()

    if not num_owned_row:
        return -1
    
    rental_count_query = """
    SELECT COUNT(*)
    FROM rental
    WHERE item_id = ?;
    """

    cur.execute(rental_count_query, (item_id,))
    active_rentals_row = cur.fetchone()
    
    return num_owned_row[0] - active_rentals_row[0]
    

def place_in_line(item_id: str = None, customer_id: str = None) -> int:
    """
    Returns the customer's place_in_line, or -1 if not on waitlist.
    """
    query = """
    SELECT place_in_line
    FROM waitlist
    WHERE item_id = ? AND
    customer_id = ?;
    """

    cur.execute(query, (item_id, customer_id, ))
    result = cur.fetchone()
    return result[0] if result else -1


def line_length(item_id: str = None) -> int:
    """
    Returns how many people are on the waitlist for this item.
    """
    query = """
    SELECT count(*)
    FROM waitlist
    WHERE item_id = ?;
    """
    cur.execute(query, (item_id,))
    result = cur.fetchone()
    print(f"Number of people in waitlist {result[0]}")
    return result[0]


def save_changes():
    """
    Commits all changes made to the db.
    """
    conn.commit()


def close_connection():
    """
    Closes the cursor and connection.
    """
    if cur:
        cur.close()
    if conn:
        conn.close()
        

