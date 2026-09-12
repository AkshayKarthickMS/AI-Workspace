# AegisOS Demo Sales Data Dictionary

`sales_data.csv` is a synthetic transaction-level B2B software sales dataset. Monetary values are expressed in USD and each row represents one completed sales transaction.

| Field | Type | Definition |
|---|---|---|
| `date` | ISO date | Date on which the transaction was recorded. |
| `region` | text | Commercial reporting region for the transaction. |
| `country` | text | Customer country within the reporting region. |
| `product` | text | AegisOS product sold. |
| `product_category` | text | Portfolio category associated with the product. |
| `customer_segment` | text | Customer size segment: Enterprise, Mid-Market, or SMB. |
| `units_sold` | integer | Number of product units included in the transaction. |
| `unit_price` | decimal | Realized selling price per unit after normal commercial variation. |
| `revenue` | decimal | Transaction revenue, equal to `units_sold × unit_price`, rounded to cents. |
| `cost` | decimal | Estimated direct cost allocated to the transaction. |
| `profit` | decimal | Transaction profit, equal to `revenue − cost`, rounded to cents. |
| `sales_channel` | text | Route to market: Direct, Partner, or Online. |
| `salesperson` | text | Fictional account executive assigned to the transaction. |
| `inventory_level` | integer | Units on hand immediately before the transaction was fulfilled. |

The data is deterministic synthetic demo data and contains no customer or employee personal data.
