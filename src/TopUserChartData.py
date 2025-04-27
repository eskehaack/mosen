import threading
from src.data_connection import get_query,get_prods
import plotly.express as px

class TopUserChartData:
    """Class to cache db callsand generate top user charts
    
    (This adds state to a stateless framework, but it works since there is only 1 client)"""
    # region Singleton pattern
    _instance = None
    _lock = threading.Lock()
    

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self,x_top=10):
        if self._initialized:
            return
        self.all_user_products = None
        self.x_top = x_top
        self.refresh()
        self._initialized = True
    # endregion

    # region bussiness logic
    def refresh(self):
        """query and cache all needed data"""
        self.all_user_products = self.get_verbose_user_products()
        self.all_products = (
            get_prods()
            .sort_values(by=["category", "name"])["name"]
            .to_list()
        )

    def get_chart(self, selected_products:list)-> px.bar:
        """returns a barchart with the top buyers of selected_products based last refresh"""
        selected_user_products = self.all_user_products[self.all_user_products['product'].isin(selected_products)]
        user_totals = (
            selected_user_products
            .groupby('user', as_index=False)['amount']
            .sum()
        )
        top_x_users = (
            user_totals
            .sort_values(by='amount', ascending=False)
            .head(self.x_top)["user"]
            .to_list()
        )
        selected_user_products = selected_user_products[selected_user_products['user'].isin(top_x_users)]
        return px.bar(selected_user_products,x="user",y="amount",color="product")
    
    def get_verbose_user_products(self):
        """get user products with all possible combinations listed (ie. all rows with amount = 0 are included)"""
        all_user_products = self.__class__.query_user_products()
        all_user_products = (
            all_user_products
            .pivot_table(index="user", columns="product", values="amount", fill_value=0)
            .reset_index()
            .melt(id_vars="user", var_name="product", value_name="amount")
        )
        return all_user_products
    # endregion

    # region DB Query Configuration
    __db_query = """
        SELECT users.name AS user,prods.name AS product, COUNT(*) AS amount
        FROM users 
            INNER JOIN transactions  ON transactions.barcode_user = users.barcode
            INNER JOIN prods ON transactions.barcode_prod = prods.barcode
        GROUP BY users.name,prods.name
    """
    __db_dtypes = {
        "user": "string",
        "product": "string",
        "amount": "int64"
    }
    __db_cols = [col for col,_ in __db_dtypes.items()]
    @classmethod
    def query_user_products(cls):
        user_products = get_query(cls.__db_query,cls.__db_cols)
        typed_user_products = user_products.astype(cls.__db_dtypes)
        return typed_user_products
    # endregion