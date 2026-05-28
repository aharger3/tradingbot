"""Position sizing for options trades. Computes contracts from $1K max loss and 2:1 RR target."""

from dataclasses import dataclass
from typing import Literal


CONTRACT_MULTIPLIER = 100  # 1 option contract = 100 shares
DEFAULT_MAX_LOSS = 1000.0  # $1K risk per trade per rules.md
DEFAULT_RR = 2.0           # 2:1 reward:risk target


@dataclass
class SizingPlan:
    """Computed trade plan: levels, contract counts, max loss/reward."""
    direction: Literal["call", "put"]
    stock_entry: float
    stock_stop: float
    stock_target: float
    stock_risk_per_share: float
    stock_reward_per_share: float
    # Option-level sizing (requires option premiums)
    contracts_estimated: int    # using delta heuristic
    contracts_formula: str      # exact formula for Austin to plug premium
    max_loss: float
    max_reward: float

    def format_discord(self) -> str:
        """Human-readable summary for Discord embed."""
        arrow = "↑" if self.direction == "call" else "↓"
        return (
            f"**{self.direction.upper()}** {arrow}\n"
            f"Entry: ${self.stock_entry:.2f}\n"
            f"Stop:  ${self.stock_stop:.2f}  (risk ${self.stock_risk_per_share:.2f}/sh)\n"
            f"Target: ${self.stock_target:.2f}  (reward ${self.stock_reward_per_share:.2f}/sh = 2R)\n"
            f"~Contracts: {self.contracts_estimated} (ATM ~0.5 delta)\n"
            f"Max loss: ${self.max_loss:.0f}  |  Max reward: ${self.max_reward:.0f}\n"
            f"Sizing formula: {self.contracts_formula}"
        )


def compute_plan(
    stock_entry: float,
    stock_stop: float,
    direction: Literal["call", "put"] = "call",
    max_loss: float = DEFAULT_MAX_LOSS,
    rr: float = DEFAULT_RR,
    assumed_delta: float = 0.5,
) -> SizingPlan:
    """
    Build trade plan from signal entry + stop.

    Stock entry/stop come from candle data. Option contracts estimated using
    a delta heuristic (ATM ~0.5). For exact contract count, Austin plugs the
    real option premium into contracts_formula.
    """
    if direction == "call":
        if stock_stop >= stock_entry:
            raise ValueError(f"Call stop ({stock_stop}) must be below entry ({stock_entry})")
        risk = stock_entry - stock_stop
        target = stock_entry + rr * risk
    else:  # put
        if stock_stop <= stock_entry:
            raise ValueError(f"Put stop ({stock_stop}) must be above entry ({stock_entry})")
        risk = stock_stop - stock_entry
        target = stock_entry - rr * risk

    reward = rr * risk

    # Option contract estimate: delta translates stock move to option move
    # option_risk_per_contract ≈ assumed_delta × stock_risk × 100
    option_risk_per_contract = assumed_delta * risk * CONTRACT_MULTIPLIER
    if option_risk_per_contract <= 0:
        contracts = 0
    else:
        contracts = int(max_loss // option_risk_per_contract)

    formula = (
        f"floor({max_loss:.0f} / ((entry_premium - stop_premium) × 100))"
    )

    return SizingPlan(
        direction=direction,
        stock_entry=round(stock_entry, 2),
        stock_stop=round(stock_stop, 2),
        stock_target=round(target, 2),
        stock_risk_per_share=round(risk, 2),
        stock_reward_per_share=round(reward, 2),
        contracts_estimated=contracts,
        contracts_formula=formula,
        max_loss=max_loss,
        max_reward=max_loss * rr,
    )


if __name__ == "__main__":
    # Sanity: TSLA call, entry $440.50, stop $439.80, $0.70 risk/share
    plan = compute_plan(stock_entry=440.50, stock_stop=439.80, direction="call")
    print(plan.format_discord())
    print()

    # Put: NVDA, entry $850, stop $852.50
    plan_put = compute_plan(stock_entry=850.0, stock_stop=852.50, direction="put")
    print(plan_put.format_discord())
