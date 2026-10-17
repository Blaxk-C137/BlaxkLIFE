"""Closed-loop BLX economy: audits, invariants, rent, wages."""

from __future__ import annotations

import pytest

from blxverse import config
from blxverse.engine.economy import VALID_CATEGORIES, EconomyError, authorize_spend
from blxverse.engine.sim import SimError


def test_starting_balance_and_ledger_header(sim):
    p = sim.player
    assert p.wallet == config.STARTING_BALANCE
    assert p.ledger == []


def test_spending_is_audited_and_balance_never_negative(sim, tmp_path, monkeypatch):
    monkeypatch.setenv("BLXVERSE_DATA_DIR", str(tmp_path))
    sim.player_spend(120, "purchase", "Test purchase", counterparty="business")
    assert sim.player.wallet == config.STARTING_BALANCE - 120
    entry = sim.player.ledger[-1]
    assert entry["amount"] == -120
    assert entry["balance_after"] == sim.player.wallet
    assert entry["category"] in VALID_CATEGORIES
    with pytest.raises(SimError) as err:
        sim.player_spend(config.STARTING_BALANCE + 1, "purchase", "Impossible")
    assert err.value.code == "insufficient_funds"
    assert sim.player.wallet == config.STARTING_BALANCE - 120


def test_authorize_spend_rejects_invalid_amounts():
    with pytest.raises(EconomyError):
        authorize_spend(100, -5)
    with pytest.raises(EconomyError):
        authorize_spend(100, config.MAX_WALLET_TXN + 1)
    with pytest.raises(EconomyError):
        authorize_spend(10, 11)


def test_remote_shopping_costs_delivery_fee(sim, run):
    from blxverse.content.items import ITEM_BY_ID
    remote = run("buy", item_id="coffee_voucher", remote=True)
    local = run("buy", item_id="cupcakes", remote=False)
    assert remote["paid"] == ITEM_BY_ID["coffee_voucher"]["price"] + 1  # 10% rounded up
    assert local["paid"] == ITEM_BY_ID["cupcakes"]["price"]


def test_daily_rent_and_income(sim):
    start = sim.player.wallet
    sim.advance((9 * 60 + 5) - (7 * 60 + 30))
    assert sim.player.wallet == start - config.DAILY_RENT
    assert any(t["category"] == "rent" for t in sim.player.ledger)


def test_street_cart_requires_capital_and_pays_daily(sim, run, at_venue):
    at_venue("square")
    with pytest.raises(SimError) as err:
        # player cannot afford 250 after we drain them below it
        sim.player.wallet = 10
        run("start_business")
    assert err.value.code == "insufficient_funds"
    sim.player.wallet = config.STREET_CART_COST
    run("start_business")
    assert sim.player.flags["cart_owned"] is True
    assert sim.player.wallet == 0
    sim.advance(60 * 12)
    assert sim.player.wallet > 0, "cart should have produced daily income at 18:00"


def test_npc_economy_moves(sim):
    sim.advance(60 * 26)
    assert any(n.bills_due >= 0 for n in sim.npcs)
    assert sum(n.wallet for n in sim.npcs) > 0


def test_food_can_be_bought_and_eaten(sim, run):
    """The cafe counter closes the energy loop: buy food, eat it, get energy back."""
    sim.player.energy = 30
    wallet = sim.player.wallet
    bought = run("buy", item_id="sandwich", remote=True)
    assert bought["ok"] and bought["consumable"] is True
    assert sim.player.inventory["sandwich"] == 1
    assert sim.player.wallet < wallet

    eaten = run("use_item", item_id="sandwich")
    assert eaten["ok"] and eaten["energy"] > 30
    assert "sandwich" not in sim.player.inventory


def test_menu_is_exposed_in_world_payload(sim):
    menu = {item["id"]: item for item in sim.world_payload()["menu"]}
    assert {"sandwich", "iced_coffee", "smoothie"} <= set(menu)
    assert all(item["energy"] > 0 for item in menu.values())
