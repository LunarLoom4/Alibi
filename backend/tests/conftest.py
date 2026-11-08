import pytest


# The columns of the table, in the order they are printed.
COLUMNS = ["passed", "failed", "errors", "skipped", "xfailed", "xpassed"]

# The results of each Test File, filled while the Tests run.
results_of_file = {}


# Returns the results of a Test File, and adds an empty row for it the first time.
def results_of(file_path: str) -> dict:
    if file_path not in results_of_file:
        results_of_file[file_path] = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0, "xpassed": 0, "seconds": 0.0}

    return results_of_file[file_path]


# Called by pytest for every report of a Test: Its setup, its call, and its teardown.
# With pytest-xdist, the Workers send every report to the main Process, so this table sees all the Tests.
def pytest_runtest_logreport(report: pytest.TestReport):
    results = results_of(report.nodeid.split("::")[0])
    results["seconds"] += report.duration

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


# Called by pytest at the end of the run, to print one line for each Test File.
# The seconds of a File are the time of its Tests added up over all the Workers, so they can be more than the time of the whole run.
def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter):
    terminalreporter.section("Tests per File")

    # The File column is as wide as the longest File path.
    width = len("File")

    for file_path in results_of_file:
        width = max(width, len(file_path))

    header = f"{'File':<{width}}"

    for column in COLUMNS:
        header += f" {column.capitalize():>8}"

    header += f" {'Seconds':>8}"
    terminalreporter.write_line(header)

    for file_path in sorted(results_of_file):
        results = results_of_file[file_path]
        line = f"{file_path:<{width}}"

        for column in COLUMNS:
            line += f" {results[column]:>8}"

        line += f" {results['seconds']:>8.2f}"
        terminalreporter.write_line(line)
