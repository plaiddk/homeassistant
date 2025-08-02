logger.info("Starting Python script: set_finish_in_relative")

# Fetch the finish time sensor
finish_time_state = hass.states.get("sensor.elpris_lavest_4t_vaskemaskine")

if finish_time_state is None:
    logger.error("Sensor 'sensor.elpris_lavest_4t_vaskemaskine' is NOT available.")
    hass.states.set("sensor.finish_in_relative", -1, {
        "unit_of_measurement": "seconds",
        "friendly_name": "Finish In Relative",
        "error": "Missing sensor.elpris_lavest_4t_vaskemaskine"
    })
else:
    finish_time = finish_time_state.state
    if not finish_time:
        logger.error("Sensor 'sensor.elpris_lavest_4t_vaskemaskine' is empty or null.")
        hass.states.set("sensor.finish_in_relative", -1, {
            "unit_of_measurement": "seconds",
            "friendly_name": "Finish In Relative",
            "error": "Empty state"
        })
    else:
        try:
            # Extract timestamp from ISO 8601 format (e.g., "2025-01-30T04:39:00+0100")
            date_time_parts = finish_time.split("T")
            date_parts = date_time_parts[0].split("-")  # YYYY-MM-DD -> [YYYY, MM, DD]
            time_parts = date_time_parts[1][:8].split(":")  # HH:MM:SS -> [HH, MM, SS]
            timezone_offset = int(date_time_parts[1][-5:]) // 100  # Extract timezone offset from "+0100"

            year = int(date_parts[0])
            month = int(date_parts[1])
            day = int(date_parts[2])
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2])

            logger.info(f"Parsed time: {year}-{month}-{day} {hour}:{minute}:{second} (UTC+{timezone_offset})")

            # ✅ DO NOT manually add or subtract timezone offset, just convert to total seconds

            # Days in each month (handling leap years)
            days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):  # Leap year
                days_in_month[1] = 29

            # Calculate total days since 1970
            total_days = sum(
                366 if (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0) else 365
                for y in range(1970, year)
            )
            total_days += sum(days_in_month[:month - 1]) + (day - 1)

            # Convert finish time to total seconds
            finish_seconds = total_days * 86400 + hour * 3600 + minute * 60 + second

            # ✅ NO timezone offset correction needed

            # Get current time from HA sensors
            current_time_state = hass.states.get("sensor.time")
            current_date_state = hass.states.get("sensor.date")
            if current_time_state is None or current_date_state is None:
                logger.error("Sensor 'sensor.time' or 'sensor.date' is not available.")
                hass.states.set("sensor.finish_in_relative", -1, {
                    "unit_of_measurement": "seconds",
                    "friendly_name": "Finish In Relative",
                    "error": "Missing time/date sensors"
                })
            else:
                current_time = current_time_state.state
                current_date = current_date_state.state
                now_date = current_date.split("-")
                now_time = current_time.split(":")
                now_year = int(now_date[0])
                now_month = int(now_date[1])
                now_day = int(now_date[2])
                now_hour = int(now_time[0])
                now_minute = int(now_time[1])

                # Convert current time to UTC timestamp
                now_total_days = sum(
                    366 if (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0) else 365
                    for y in range(1970, now_year)
                )
                now_total_days += sum(days_in_month[:now_month - 1]) + (now_day - 1)

                current_seconds = now_total_days * 86400 + now_hour * 3600 + now_minute * 60

                logger.info(f"Current UTC timestamp (seconds since 1970): {current_seconds}")

                # Calculate difference
                start_seconds = finish_seconds - current_seconds
                logger.info(f"Calculated time until finish: {start_seconds} seconds")

                # Set Home Assistant sensor
                hass.states.set("sensor.finish_in_relative", start_seconds, {
                    "unit_of_measurement": "seconds",
                    "friendly_name": "Finish In Relative"
                })
                logger.info(f"Sensor 'sensor.finish_in_relative' set to {start_seconds} seconds.")

        except Exception as e:
            logger.error(f"Error processing time: {e}")
            hass.states.set("sensor.finish_in_relative", -1, {
                "unit_of_measurement": "seconds",
                "friendly_name": "Finish In Relative",
                "error": str(e)
            })
