# Transit Database - Schema Analysis

## 1. Schema Decisions: Natural vs Surrogate Keys?

I use a **hybrid approach** combining both natural and surrogate keys:

**Surrogate Keys:**
- `lines.line_id` - SERIAL PRIMARY KEY
- `stops.stop_id` - SERIAL PRIMARY KEY  
- `stop_events.event_id` - SERIAL PRIMARY KEY

**Rationale:** Surrogate keys provide stability, better join performance, and simplify foreign key relationships. They don't change when business requirements evolve.

**Natural Keys:**
- `trips.trip_id` - VARCHAR(20) PRIMARY KEY (e.g., 'T0001')

**Rationale:** Trip IDs come directly from CSV data and are meaningful business identifiers. Using natural keys here avoids unnecessary lookups during data loading and maintains consistency with external systems.

**Composite Keys:**
- `line_stops(line_id, stop_id)` - Prevents duplicate stops on same line
- `line_stops(line_id, sequence_number)` - Ensures unique sequence positions

## 2. Constraints: What CHECK/UNIQUE Constraints?

**CHECK Constraints:**
1. `vehicle_type IN ('rail', 'bus')` - Enforces valid vehicle types
2. `time_offset_minutes >= 0 AND time_offset_minutes <= 1440` - Validates time is within 24 hours
3. `passengers_on >= 0` and `passengers_off >= 0` - Prevents negative passenger counts

**UNIQUE Constraints:**
1. `lines.line_name UNIQUE` - One route name per line
2. `line_stops(line_id, stop_id)` - No duplicate stop assignments on same route
3. `line_stops(line_id, sequence_number)` - No duplicate sequence positions  
4. `stop_events(trip_id, stop_id)` - One event per stop per trip

These constraints ensure data integrity and prevent logical errors like assigning the same stop to multiple sequence positions.

## 3. Complex Query: Which Query Was Hardest?

**Q10** was the most challenging query:

```sql
SELECT s.stop_name, SUM(se.passengers_on) as total_boardings
FROM stops s
JOIN stop_events se ON s.stop_id = se.stop_id
GROUP BY s.stop_id, s.stop_name
HAVING SUM(se.passengers_on) > (
    SELECT AVG(total)
    FROM (
        SELECT SUM(passengers_on) as total
        FROM stop_events
        GROUP BY stop_id
    ) as stop_totals
)
```

**Why it's complex:**
1. **Double aggregation** - Inner subquery aggregates by stop_id, outer query aggregates the averages
2. **Correlated subquery in HAVING** - Computes average using nested subquery
3. **Mental model** - Requires understanding that I am comparing each stop's total against the average of all stops' totals
4. **NULL handling** - Potential edge cases with stops having no events

## 4. Foreign Keys: Invalid Data Prevention

Foreign keys with ON DELETE CASCADE prevent **orphaned records** and **invalid references**:

**Example Scenario:**
Without foreign keys, you could insert a `stop_events` record referencing a `trip_id` that doesn't exist. Or, if you delete a line, you'd leave hanging references in `line_stops`, `trips`, and `stop_events`.

**My Implementation:**
```sql
-- line_stops references lines
line_id INTEGER REFERENCES lines(line_id) ON DELETE CASCADE

-- trips references lines  
line_id INTEGER NOT NULL REFERENCES lines(line_id) ON DELETE CASCADE

-- stop_events references trips and stops
trip_id VARCHAR(20) NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE
stop_id INTEGER NOT NULL REFERENCES stops(stop_id) ON DELETE CASCADE
```

**What this prevents:**
- **Orphaned records**: Deleting Line 20 cascades to all its stops, trips, and events
- **Invalid inserts**: Cannot insert a `trips` record with `line_id = 999` if it doesn't exist
- **Referential integrity**: Database enforces logical consistency automatically

## 5. Why SQL for This Domain? When Relational?

SQL is ideal for transit data because:

**1. Relational Nature**
- Lines have many stops (1:N)
- Trips belong to one line (N:1)
- Stop events belong to one trip and one stop
- These relationships map naturally to foreign keys and JOINs

**2. Complex Queries**
- **Q5**: Finding routes serving two specific stops uses natural set intersection
- **Q8/Q9**: Delay analysis requires comparing actual vs scheduled times across multiple tables
- **Q10**: Statistical comparison leverages nested aggregations

**3. Data Integrity**
- Foreign keys ensure a trip always references a valid line
- UNIQUE constraints prevent duplicate stop sequences
- CHECK constraints validate business rules (positive passenger counts)

**4. Performance**
- Indexes on foreign keys accelerate JOINs
- Query optimizer handles multi-table queries efficiently
- Supports time-series analysis on 11,000+ events


**When Non-Relational Would Suffer:**
NoSQL databases struggle with joins across collections. Finding all stops for trip T0001 would require multiple queries or denormalization, increasing complexity and maintenance burden.