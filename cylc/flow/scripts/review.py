from cylc.flow.review import CylcReviewService
from cylc.flow.ws import ws_cli

def main():
    ws_cli(CylcReviewService, "")