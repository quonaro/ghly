#!/bin/bash
# Load testing script for GitHub proxy API

set -euo pipefail

# Default values
REQUESTS=1000
CONCURRENT=100
RPS=""
DURATION=60
URL=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
show_help() {
    cat << EOF
Usage: $0 <URL> [OPTIONS]

Load testing script for GitHub proxy API

Arguments:
  URL                    Full URL to test (e.g., http://localhost:8000/gh/owner/repo/path?ref=main)

Options:
  -n, --requests NUM     Total number of requests to make (default: 1000)
  -c, --concurrent NUM   Number of concurrent requests (default: 100)
  --rps NUM              Target requests per second (uses duration mode)
  --duration SECONDS     Duration in seconds for RPS mode (default: 60)
  -h, --help             Show this help message

Examples:
  # Run 10000 requests with 100 concurrent connections
  $0 http://localhost:8000/gh/quonaro/Specula/specula.js?ref=standalone -n 10000 -c 100

  # Run for 60 seconds targeting 500 RPS
  $0 http://localhost:8000/gh/quonaro/Specula/specula.js?ref=standalone --rps 500 --duration 60
EOF
}

parse_args() {
    if [ $# -eq 0 ]; then
        show_help
        exit 1
    fi

    URL="$1"
    shift

    while [[ $# -gt 0 ]]; do
        case $1 in
            -n|--requests)
                REQUESTS="$2"
                shift 2
                ;;
            -c|--concurrent)
                CONCURRENT="$2"
                shift 2
                ;;
            --rps)
                RPS="$2"
                shift 2
                ;;
            --duration)
                DURATION="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Make a single request and record statistics
make_request() {
    local url="$1"
    local result_file="$2"
    local start_time
    
    start_time=$(date +%s.%N)
    
    if response=$(curl -s -w "\n%{http_code}\n%{time_total}" -o /dev/null --max-time 30 "$url" 2>&1); then
        local end_time
        end_time=$(date +%s.%N)
        local response_time
        response_time=$(echo "$response" | tail -n 1)
        local status_code
        status_code=$(echo "$response" | tail -n 2 | head -n 1)
        
        echo "$response_time|$status_code|" >> "$result_file"
    else
        local end_time
        end_time=$(date +%s.%N)
        local elapsed
        elapsed=$(echo "$end_time - $start_time" | bc)
        echo "$elapsed|0|$response" >> "$result_file"
    fi
}

# Run load test with fixed requests and concurrency
run_load_test() {
    local url="$1"
    local total_requests="$2"
    local concurrent="$3"
    local result_file
    result_file=$(mktemp)
    local pids=()
    local semaphore
    semaphore=$(mktemp -u)
    mkfifo "$semaphore"
    
    # Initialize semaphore
    for ((i=0; i<concurrent; i++)); do
        echo > "$semaphore"
    done
    
    echo "Starting load test..."
    echo "URL: $url"
    echo "Mode: Fixed requests ($total_requests requests, $concurrent concurrent)"
    
    local start_time
    start_time=$(date +%s.%N)
    
    for ((i=1; i<=total_requests; i++)); do
        read -r < "$semaphore"
        (
            make_request "$url" "$result_file"
            echo > "$semaphore"
        ) &
        pids+=($!)
    done
    
    # Wait for all background jobs
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
    
    local end_time
    end_time=$(date +%s.%N)
    
    rm -f "$semaphore"
    
    print_stats "$result_file" "$start_time" "$end_time"
    rm -f "$result_file"
}

# Run RPS test
run_rps_test() {
    local url="$1"
    local target_rps="$2"
    local duration="$3"
    local result_file
    result_file=$(mktemp)
    local interval
    interval=$(echo "scale=6; 1.0 / $target_rps" | bc)
    local pids=()
    
    echo "Starting load test..."
    echo "URL: $url"
    echo "Mode: RPS target ($target_rps RPS for $duration seconds)"
    
    local start_time
    start_time=$(date +%s.%N)
    local end_time
    end_time=$(echo "$start_time + $duration" | bc)
    
    while true; do
        local current_time
        current_time=$(date +%s.%N)
        
        if (( $(echo "$current_time >= $end_time" | bc -l) )); then
            break
        fi
        
        # Launch request in background
        make_request "$url" "$result_file" &
        pids+=($!)
        
        # Sleep for interval
        sleep "$interval"
    done
    
    # Wait for all background jobs
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
    
    local final_time
    final_time=$(date +%s.%N)
    
    print_stats "$result_file" "$start_time" "$final_time"
    rm -f "$result_file"
}

# Print statistics
print_stats() {
    local result_file="$1"
    local start_time="$2"
    local end_time="$3"
    
    local duration
    duration=$(echo "$end_time - $start_time" | bc)
    
    if (( $(echo "$duration == 0" | bc -l) )); then
        return
    fi
    
    # Parse results
    local total_requests=0
    local successful=0
    local failed=0
    declare -A status_codes
    local response_times=()
    declare -A errors
    
    while IFS='|' read -r response_time status_code error; do
        ((total_requests++))
        
        if [ -n "$status_code" ] && [ "$status_code" -ge 200 ] && [ "$status_code" -lt 300 ]; then
            ((successful++))
        else
            ((failed++))
            if [ -n "$error" ]; then
                errors["$error"]=$((${errors["$error"]:-0} + 1))
            fi
        fi
        
        if [ -n "$status_code" ]; then
            status_codes["$status_code"]=$((${status_codes["$status_code"]:-0} + 1))
        else
            status_codes["0"]=$((${status_codes["0"]:-0} + 1))
        fi
        
        if [ -n "$response_time" ]; then
            response_times+=("$response_time")
        fi
    done < "$result_file"
    
    local rps
    rps=$(echo "scale=2; $total_requests / $duration" | bc)
    local success_percent
    success_percent=$(echo "scale=1; $successful * 100 / $total_requests" | bc)
    local fail_percent
    fail_percent=$(echo "scale=1; $failed * 100 / $total_requests" | bc)
    
    echo ""
    echo "============================================================"
    echo "LOAD TEST RESULTS"
    echo "============================================================"
    printf "Total requests:      %d\n" "$total_requests"
    printf "Duration:            %.2f seconds\n" "$duration"
    printf "Requests per second: %.2f RPS\n" "$rps"
    printf "Successful:         %d (%.1f%%)\n" "$successful" "$success_percent"
    printf "Failed:              %d (%.1f%%)\n" "$failed" "$fail_percent"
    
    echo ""
    echo "Status codes:"
    for code in $(printf '%s\n' "${!status_codes[@]}" | sort -n); do
        local count=${status_codes["$code"]}
        local percent
        percent=$(echo "scale=1; $count * 100 / $total_requests" | bc)
        printf "  %s: %d (%.1f%%)\n" "$code" "$count" "$percent"
    done
    
    if [ ${#response_times[@]} -gt 0 ]; then
        # Calculate min, max, mean, median
        local sorted_times
        sorted_times=$(printf '%s\n' "${response_times[@]}" | sort -n)
        local min
        min=$(echo "$sorted_times" | head -n 1)
        local max
        max=$(echo "$sorted_times" | tail -n 1)
        
        local sum=0
        for time in "${response_times[@]}"; do
            sum=$(echo "$sum + $time" | bc)
        done
        local mean
        mean=$(echo "scale=4; $sum / ${#response_times[@]}" | bc)
        
        local median
        local mid=$(( ${#response_times[@]} / 2 ))
        if [ $(( ${#response_times[@]} % 2 )) -eq 0 ]; then
            local val1
            val1=$(echo "$sorted_times" | sed -n "${mid}p")
            local val2
            val2=$(echo "$sorted_times" | sed -n "$((mid+1))p")
            median=$(echo "scale=4; ($val1 + $val2) / 2" | bc)
        else
            median=$(echo "$sorted_times" | sed -n "$((mid+1))p")
        fi
        
        echo ""
        echo "Response times (seconds):"
        printf "  Min:    %.4f\n" "$min"
        printf "  Max:    %.4f\n" "$max"
        printf "  Mean:   %.4f\n" "$mean"
        printf "  Median: %.4f\n" "$median"
    fi
    
    if [ ${#errors[@]} -gt 0 ]; then
        echo ""
        printf "Errors (%d):\n" "${#errors[@]}"
        local count=0
        for error in $(printf '%s\n' "${!errors[@]}" | sort -rn -k2); do
            if [ $count -lt 10 ]; then
                printf "  %s: %d\n" "$error" "${errors["$error"]}"
                ((count++))
            fi
        done
        if [ ${#errors[@]} -gt 10 ]; then
            printf "  ... and %d more errors\n" "$(( ${#errors[@]} - 10 ))"
        fi
    fi
    
    echo "============================================================"
}

# Main
main() {
    parse_args "$@"
    
    # Check if bc is available
    if ! command -v bc &> /dev/null; then
        echo "Error: 'bc' command is required but not installed."
        echo "Install it with: sudo apt-get install bc (Debian/Ubuntu) or brew install bc (macOS)"
        exit 1
    fi
    
    # Check if curl is available
    if ! command -v curl &> /dev/null; then
        echo "Error: 'curl' command is required but not installed."
        exit 1
    fi
    
    if [ -n "$RPS" ]; then
        run_rps_test "$URL" "$RPS" "$DURATION"
    else
        run_load_test "$URL" "$REQUESTS" "$CONCURRENT"
    fi
}

main "$@"

