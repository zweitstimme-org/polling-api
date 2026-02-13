# Working with the API in R

A comprehensive guide to accessing German polling data using R and the `httr2` package.

## Installation

First, install the required packages:

```r
# Install httr2 for API requests
install.packages("httr2")

# Install supporting packages for data manipulation and visualization
install.packages(c("dplyr", "ggplot2", "lubridate", "tidyr", "jsonlite"))

# Load libraries
library(httr2)
library(dplyr)
library(ggplot2)
library(lubridate)
library(tidyr)
```

## API Basics

### Base URL

```r
BASE_URL <- "https://api.fasttrack29.com/v1"
```

### Making Your First Request

```r
# Create a simple GET request
response <- request(BASE_URL) |>
  req_url_path("/polls") |>
  req_url_query(limit = 5) |>
  req_perform()

# Check if request was successful
resp_status(response)  # Should return 200

# Parse JSON response
data <- resp_body_json(response, simplifyVector = TRUE)

# View the structure
str(data)
```

## Use Case 1: Get Latest Federal Polls

**Goal**: Retrieve the most recent federal election polls with party results.

```r
get_latest_federal_polls <- function(n = 10) {
  request(BASE_URL) |>
    req_url_path("/polls") |>
    req_url_query(
      scope = "federal",
      limit = n,
      include_results = "true"
    ) |>
    req_perform() |>
    resp_body_json(simplifyVector = TRUE)
}

# Get latest 10 federal polls
latest_polls <- get_latest_federal_polls(10)

# Extract the polls data
polls_df <- as_tibble(latest_polls$items)

# Display key information
polls_df |>
  select(id, publish_date, institute_name, respondents, election_type) |>
  head()
```

### Visualizing Latest Results

```r
# Extract party results from nested structure
extract_results <- function(polls_data) {
  results_list <- lapply(polls_data$items, function(poll) {
    if (length(poll$results) > 0) {
      res <- as_tibble(poll$results)
      res$publish_date <- poll$publish_date
      res$institute <- poll$institute_name
      return(res)
    }
    return(NULL)
  })
  
  bind_rows(results_list)
}

# Get results
results_df <- extract_results(latest_polls)

# Plot latest poll results
results_df |>
  filter(publish_date == max(publish_date)) |>
  ggplot(aes(x = reorder(party_short_name, -percentage), y = percentage, fill = party_short_name)) +
  geom_col() +
  labs(
    title = "Latest Federal Election Poll",
    subtitle = paste("Published:", max(results_df$publish_date)),
    x = "Party",
    y = "Percentage",
    fill = "Party"
  ) +
  theme_minimal() +
  theme(legend.position = "none")
```

## Use Case 2: Track Party Support Over Time

**Goal**: Analyze how a specific party's support has changed over the past year.

```r
get_party_trend <- function(party_id, months = 12) {
  # Calculate date range
  end_date <- Sys.Date()
  start_date <- end_date - months(months)
  
  # Fetch polls with date filter
  request(BASE_URL) |>
    req_url_path("/results") |>
    req_url_query(
      party_id = party_id,
      scope = "federal",
      date_from = as.character(start_date),
      date_to = as.character(end_date),
      limit = 500
    ) |>
    req_perform() |>
    resp_body_json(simplifyVector = TRUE)
}

# Get CDU/CSU trend (party_id = 1)
cdu_trend <- get_party_trend(1, 12)

# Process data
cdu_data <- cdu_trend$items |>
  as_tibble() |>
  mutate(publish_date = as.Date(publish_date))

# Plot trend
cdu_data |>
  unnest(results) |>
  ggplot(aes(x = publish_date, y = percentage)) +
  geom_line(color = "black", linewidth = 1) +
  geom_point(alpha = 0.5) +
  geom_smooth(method = "loess", se = TRUE, alpha = 0.2) +
  labs(
    title = "CDU/CSU Support Over Time",
    subtitle = "Federal Election Polls",
    x = "Date",
    y = "Percentage",
    caption = "Source: Zweitstimme Polling API"
  ) +
  theme_minimal() +
  scale_y_continuous(limits = c(0, 50))
```

## Use Case 3: Compare Institute Methodologies

**Goal**: Compare how different polling institutes report results.

```r
get_institute_comparison <- function(institute_id, limit = 100) {
  request(BASE_URL) |>
    req_url_path("/polls") |>
    req_url_query(
      institute_id = institute_id,
      scope = "federal",
      limit = limit,
      include_results = "true"
    ) |>
    req_perform() |>
    resp_body_json(simplifyVector = TRUE)
}

# Get reference data to map institute IDs
get_reference_data <- function() {
  request(BASE_URL) |>
    req_url_path("/reference/all") |>
    req_perform() |>
    resp_body_json(simplifyVector = TRUE)
}

# Fetch reference data
ref_data <- get_reference_data()
institutes <- as_tibble(ref_data$institutes)

# Get data for major institutes
forsa_data <- get_institute_comparison(1)  # Forsa
insa_data <- get_institute_comparison(2)   # INSA
fgw_data <- get_institute_comparison(3)    # Forschungsgruppe Wahlen

# Combine and analyze
combine_institute_data <- function(...) {
  datasets <- list(...)
  combined <- lapply(names(datasets), function(name) {
    df <- as_tibble(datasets[[name]]$items)
    df$institute <- name
    return(df)
  })
  bind_rows(combined)
}

institute_comparison <- combine_institute_data(
  Forsa = forsa_data,
  INSA = insa_data,
  FGW = fgw_data
)

# Plot comparison (showing SPD results as example)
institute_comparison |>
  unnest(results) |>
  filter(party_id == 2) |>  # SPD
  mutate(publish_date = as.Date(publish_date)) |>
  ggplot(aes(x = publish_date, y = percentage, color = institute)) +
  geom_line(linewidth = 1) +
  labs(
    title = "SPD Polling Results by Institute",
    x = "Date",
    y = "Percentage",
    color = "Institute"
  ) +
  theme_minimal()
```

## Use Case 4: Calculate Poll Averages

**Goal**: Calculate rolling averages to smooth out polling noise.

```r
calculate_poll_averages <- function(scope = "federal", days = 14) {
  # Get all recent polls
  end_date <- Sys.Date()
  start_date <- end_date - days(days * 3)  # Get extra data for rolling window
  
  response <- request(BASE_URL) |>
    req_url_path("/results") |>
    req_url_query(
      scope = scope,
      date_from = as.character(start_date),
      date_to = as.character(end_date),
      limit = 1000
    ) |>
    req_perform()
  
  data <- resp_body_json(response, simplifyVector = TRUE)
  
  # Process results
  results_df <- data$items |>
    as_tibble() |>
    mutate(publish_date = as.Date(publish_date)) |>
    unnest(results) |>
    select(publish_date, party_id, party_short_name, percentage)
  
  # Calculate rolling averages
  results_df |>
    arrange(party_id, publish_date) |>
    group_by(party_id, party_short_name) |>
    mutate(
      rolling_avg = zoo::rollmean(percentage, k = 5, fill = NA, align = "right")
    ) |>
    ungroup()
}

# Calculate averages
poll_averages <- calculate_poll_averages("federal", 30)

# Plot
poll_averages |>
  ggplot(aes(x = publish_date, y = rolling_avg, color = party_short_name)) +
  geom_line(linewidth = 1.2) +
  labs(
    title = "14-Day Rolling Average of Party Support",
    subtitle = "Federal Election Polls",
    x = "Date",
    y = "Percentage",
    color = "Party"
  ) +
  theme_minimal() +
  theme(legend.position = "bottom")
```

## Use Case 5: Compare State vs Federal Polling

**Goal**: Compare polling trends in a specific state vs federal trends.

```r
compare_state_federal <- function(state_code = "bayern", party_id = 1) {
  # Get federal polls
  federal_response <- request(BASE_URL) |>
    req_url_path("/results") |>
    req_url_query(
      scope = "federal",
      party_id = party_id,
      limit = 200
    ) |>
    req_perform()
  
  # Get state polls
  state_response <- request(BASE_URL) |>
    req_url_path("/results") |>
    req_url_query(
      scope = state_code,
      party_id = party_id,
      limit = 200
    ) |>
    req_perform()
  
  # Process both
  federal_data <- resp_body_json(federal_response, simplifyVector = TRUE)$items |>
    as_tibble() |>
    mutate(
      publish_date = as.Date(publish_date),
      scope = "Federal"
    ) |>
    unnest(results)
  
  state_data <- resp_body_json(state_response, simplifyVector = TRUE)$items |>
    as_tibble() |>
    mutate(
      publish_date = as.Date(publish_date),
      scope = tools::toTitleCase(state_code)
    ) |>
    unnest(results)
  
  # Combine
  bind_rows(federal_data, state_data)
}

# Compare Bayern vs Federal for CDU/CSU
bayern_comparison <- compare_state_federal("bayern", 1)

# Plot comparison
bayern_comparison |>
  ggplot(aes(x = publish_date, y = percentage, color = scope)) +
  geom_line(linewidth = 1) +
  geom_smooth(method = "loess", se = FALSE) +
  labs(
    title = "CDU/CSU: Federal vs Bavaria",
    x = "Date",
    y = "Percentage",
    color = "Scope"
  ) +
  theme_minimal()
```

## Use Case 6: Export Data for External Analysis

**Goal**: Download data for use in Excel, SPSS, or other tools.

```r
export_poll_data <- function(filename = "polling_data.csv", scope = "federal") {
  # Fetch data
  response <- request(BASE_URL) |>
    req_url_path("/results") |>
    req_url_query(
      scope = scope,
      limit = 2000
    ) |>
    req_perform()
  
  data <- resp_body_json(response, simplifyVector = TRUE)
  
  # Flatten nested structure
  flat_data <- data$items |>
    as_tibble() |>
    unnest(results, names_sep = "_") |>
    mutate(publish_date = as.Date(publish_date))
  
  # Export to CSV
  write.csv(flat_data, filename, row.names = FALSE)
  message(paste("Data exported to:", filename))
  message(paste("Rows exported:", nrow(flat_data)))
  
  return(flat_data)
}

# Export data
polling_data <- export_poll_data("german_polling_data.csv", "federal")
```

## Error Handling

### Robust Request Function

```r
safe_api_request <- function(req) {
  tryCatch(
    {
      response <- req_perform(req)
      
      # Check status code
      status <- resp_status(response)
      if (status != 200) {
        warning(paste("API returned status:", status))
        return(NULL)
      }
      
      resp_body_json(response, simplifyVector = TRUE)
    },
    error = function(e) {
      message(paste("Error making request:", conditionMessage(e)))
      return(NULL)
    }
  )
}

# Usage
response <- safe_api_request(
  request(BASE_URL) |> req_url_path("/polls") |> req_url_query(limit = 10)
)
```

### Rate Limiting

```r
# Add delay between requests to be respectful
make_delayed_request <- function(req, delay = 0.5) {
  Sys.sleep(delay)
  req_perform(req)
}

# Batch request with delays
fetch_multiple_pages <- function(n_pages = 5) {
  all_data <- list()
  
  for (i in 1:n_pages) {
    response <- request(BASE_URL) |>
      req_url_path("/polls") |>
      req_url_query(
        limit = 100,
        offset = (i - 1) * 100
      ) |>
      make_delayed_request(delay = 0.5)
    
    data <- resp_body_json(response, simplifyVector = TRUE)
    all_data[[i]] <- data$items
    
    message(paste("Fetched page", i, "of", n_pages))
  }
  
  bind_rows(all_data)
}
```

## Helper Functions

### Get Party ID by Name

```r
get_party_id <- function(party_name) {
  ref_data <- get_reference_data()
  parties <- as_tibble(ref_data$parties)
  
  # Search by short name or full name
  match <- parties |>
    filter(
      short_name == party_name | 
      name == party_name |
      grepl(party_name, name, ignore.case = TRUE)
    )
  
  if (nrow(match) == 0) {
    stop(paste("Party not found:", party_name))
  }
  
  return(match$id[1])
}

# Usage
cdu_id <- get_party_id("CDU/CSU")
spd_id <- get_party_id("SPD")
```

### Create Coalition Scenarios

```r
analyze_coalition <- function(poll_id, coalition_parties) {
  # Get specific poll
  response <- request(BASE_URL) |>
    req_url_path(paste0("/polls/", poll_id)) |>
    req_perform()
  
  poll_data <- resp_body_json(response, simplifyVector = TRUE)
  
  # Extract results
  results <- as_tibble(poll_data$results)
  
  # Calculate coalition total
  coalition_sum <- results |>
    filter(party_id %in% coalition_parties) |>
    pull(percentage) |>
    sum()
  
  # Check if majority (>50%)
  majority <- coalition_sum > 50
  
  list(
    poll_id = poll_id,
    total = coalition_sum,
    majority = majority,
    parties = results |> filter(party_id %in% coalition_parties)
  )
}

# Example: CDU/CSU + SPD (Grand Coalition)
analyze_coalition(8923, c(1, 2))  # CDU/CSU + SPD
```

## Summary

This vignette demonstrated how to:

1. **Retrieve latest polls** with party breakdowns
2. **Track trends** over time for specific parties
3. **Compare institutes** and their methodologies
4. **Calculate rolling averages** to smooth polling noise
5. **Compare state vs federal** polling
6. **Export data** for external analysis
7. **Handle errors** and implement rate limiting
8. **Analyze coalition** scenarios

The API provides structured access to German polling data, and with `httr2`, R users can easily fetch, analyze, and visualize this data for research, journalism, or political analysis.

For more information about available endpoints, see the [API Reference](api.md).
