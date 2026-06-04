## 2025-05-15 - [Negative Input Vulnerability in Stat Allocation]
**Vulnerability:** The `/allocate_stat` endpoint allowed negative values for the `points` parameter, enabling players to increase their total `stat_points` instead of consuming them.
**Learning:** Business logic that performs subtraction (e.g., `total -= cost`) must always validate that the `cost` is non-negative to prevent unintended balance increases.
**Prevention:** Use Pydantic's `Field(gt=0)` for input validation in FastAPI/Pydantic models to enforce positive values at the schema level.
