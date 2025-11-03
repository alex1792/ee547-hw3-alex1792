CREATE TABLE lines (
    line_id SERIAL PRIMARY KEY,  -- or use line_name as natural key?
    line_name VARCHAR(50) NOT NULL UNIQUE,
    vehicle_type VARCHAR(10) CHECK (vehicle_type IN ('rail', 'bus'))
);

CREATE TABLE stops (
    -- Your design here
    stop_id SERIAL PRIMARY KEY,
    stop_name VARCHAR(100) NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8)
);

CREATE TABLE line_stops (
    -- Your design here
    -- Must handle: line_id, stop_id, sequence_number, time_offset_minutes
    line_id INTEGER REFERENCES lines(line_id) ON DELETE CASCADE,
    stop_id INTEGER REFERENCES stops(stop_id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    time_offset_minutes INTEGER NOT NULL CHECK (time_offset_minutes >= 0 AND time_offset_minutes <= 1440),
    PRIMARY KEY (line_id, stop_id),  -- Prevent duplicate stops on same line
    UNIQUE (line_id, sequence_number)  -- Ensure unique sequence per line
);

-- Continue for trips and stop_events
-- Trips table: line, departure time, vehicle ID
CREATE TABLE trips (
    trip_id VARCHAR(20) PRIMARY KEY,
    line_id INTEGER NOT NULL REFERENCES lines(line_id) ON DELETE CASCADE,
    scheduled_start_time TIMESTAMP NOT NULL,
    vehicle_id VARCHAR(20) NOT NULL
);

-- Stop_Events table: Individual stop visits during a trip
CREATE TABLE stop_events (
    event_id SERIAL PRIMARY KEY,
    trip_id VARCHAR(20) NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    stop_id INTEGER NOT NULL REFERENCES stops(stop_id) ON DELETE CASCADE,
    scheduled_arrival_time TIMESTAMP NOT NULL,
    actual_arrival_time TIMESTAMP NOT NULL,
    passengers_on INTEGER NOT NULL CHECK (passengers_on >= 0),
    passengers_off INTEGER NOT NULL CHECK (passengers_off >= 0),
    UNIQUE (trip_id, stop_id)  -- Prevent duplicate events for same stop in same trip
);

-- Create indexes for better query performance
CREATE INDEX idx_line_stops_line ON line_stops(line_id);
CREATE INDEX idx_line_stops_stop ON line_stops(stop_id);
CREATE INDEX idx_trips_line ON trips(line_id);
CREATE INDEX idx_stop_events_trip ON stop_events(trip_id);
CREATE INDEX idx_stop_events_stop ON stop_events(stop_id);
CREATE INDEX idx_stop_events_time ON stop_events(actual_arrival_time);