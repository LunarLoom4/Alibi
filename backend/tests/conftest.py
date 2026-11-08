import pytest


# The columns of counts in the table, in the order they are printed.
COLUMNS = ["passed", "failed", "errors", "skipped", "xfailed", "xpassed"]

# The results of each Test File, filled while the Tests run.
results_of_file = {}


# Returns the results of a Test File, and adds an empty row for it the first time.
def results_of(file_path: str) -> dict:
    if file_path not in results_of_file:
        results_of_file[file_path] = {
            "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0, "xpassed": 0,
            "work_seconds": 0.0, "first_start": None, "last_stop": None,
        }

    return results_of_file[file_path]


# Called by pytest for every report of a Test: Its setup, its call, and its teardown.
# With pytest-xdist, the Workers send every report to the main Process, so this table sees all the Tests.
def pytest_runtest_logreport(report: pytest.TestReport):
    results = results_of(report.nodeid.split("::")[0])

    # The work time adds up every report, even when several Workers run the Tests of a File at the same time.
    results["work_seconds"] += report.duration

    # The Wall-Clock Time runs from the start of the first report of a File to the end of its last report.
    # The report of a crashed Worker has no times (start and stop are 0), so it is left out.
    if report.start > 0:
        if results["first_start"] is None or report.start < results["first_start"]:
            results["first_start"] = report.start

        if results["last_stop"] is None or report.stop > results["last_stop"]:
            results["last_stop"] = report.stop

    # Counted as pytest counts it: A Test marked 'xfail' is "xfailed" or "xpassed", and a failed setup or teardown is an error.
    if hasattr(report, "wasxfail"):
        if report.skipped:
            results["xfailed"] += 1
        else:
            results["xpassed"] += 1

    elif report.when == "call" and report.passed:
        results["passed"] += 1

    elif report.when == "call" and report.failed:
        results["failed"] += 1

    # A crashed Worker sends one failed report for its Test, marked "???" instead of setup, call or teardown. pytest counts it as failed.
    elif report.when == "???" and report.failed:
        results["failed"] += 1

    elif report.failed:
        results["errors"] += 1

    elif report.skipped:
        results["skipped"] += 1


# Called by pytest for every report of collecting a Test File.
# A File that cannot be imported, or is skipped as a whole, sends no Test reports, so it is counted here.
def pytest_collectreport(report: pytest.CollectReport):
    file_path = report.nodeid.split("::")[0]

    # Only a failed or skipped File counts. The report of the whole run has no File path.
    if report.passed or file_path == "":
        return

    results = results_of(file_path)

    if report.failed:
        results["errors"] += 1
    else:
        results["skipped"] += 1


# Called by pytest at the end of the run, to print one line for each Test File, and what the two times mean.
def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter):
    terminalreporter.write_line("")
    terminalreporter.section("Result of Tests per File")

    # The File column is as wide as the longest File path.
    width = len("File")

    for file_path in results_of_file:
        width = max(width, len(file_path))

    header = f"{'File':<{width}}"

    for column in COLUMNS:
        header += f" {column.capitalize():>8}"

    header += f" {'Wall-Clock Seconds':>19} {'Work Seconds':>13}"
    terminalreporter.write_line(header)

    for file_path in sorted(results_of_file):
        results = results_of_file[file_path]
        line = f"{file_path:<{width}}"

        for column in COLUMNS:
            line += f" {results[column]:>8}"

        # A File that was never run, because it could not be imported or was skipped as a whole, has no Wall-Clock time.
        wall_clock_seconds = 0.0

        if results["first_start"] is not None:
            wall_clock_seconds = results["last_stop"] - results["first_start"]

        line += f" {wall_clock_seconds:>19.2f} {results['work_seconds']:>13.2f}"
        terminalreporter.write_line(line)

    terminalreporter.write_line("")
    terminalreporter.write_line("Work Seconds: Cummulative Sum over the time taken by each Worker to process an entire file.")
    terminalreporter.write_line("Wall-Clock Seconds: Real time taken by all the Workers together to process an entire file.")
