import random
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
)
from eth2spec.test.helpers.constants import (
    MAINNET, MINIMAL,
)
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
    compute_committee_indices,
    get_committee_indices,
    run_sync_committee_processing,
    run_successful_sync_committee_test,
)
from eth2spec.test.context import (
    with_altair_and_later,
    with_presets,
    spec_state_test,
    always_bls,
)


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_bad_domain(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    rng = random.Random(2020)
    random_participant = rng.choice(committee_indices)

    block = build_empty_block_for_next_slot(spec, state)
    # Exclude one participant whose signature was included.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[index != random_participant for index in committee_indices],
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            committee_indices,  # full committee signs
            domain_type=spec.DOMAIN_BEACON_ATTESTER,  # Incorrect domain
        )
    )
    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_missing_participant(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    rng = random.Random(2020)
    random_participant = rng.choice(committee_indices)

    block = build_empty_block_for_next_slot(spec, state)
    # Exclude one participant whose signature was included.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[index != random_participant for index in committee_indices],
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            committee_indices,  # full committee signs
        )
    )
    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_no_participants(spec, state):
    block = build_empty_block_for_next_slot(spec, state)
    # No participants is an allowed case, but needs a specific signature, not the full-zeroed signature.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[False] * len(block.body.sync_aggregate.sync_committee_bits),
        sync_committee_signature=b'\x00' * 96
    )
    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)

# No-participants, with valid signature, is tested in test_sync_committee_rewards_empty_participants already.


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_infinite_signature_with_all_participants(spec, state):
    block = build_empty_block_for_next_slot(spec, state)
    # Include all participants, try the special-case signature for no-participants
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(block.body.sync_aggregate.sync_committee_bits),
        sync_committee_signature=spec.G2_POINT_AT_INFINITY
    )
    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_infinite_signature_with_single_participant(spec, state):
    block = build_empty_block_for_next_slot(spec, state)
    # Try include a single participant with the special-case signature for no-participants.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] + ([False] * (len(block.body.sync_aggregate.sync_committee_bits) - 1)),
        sync_committee_signature=spec.G2_POINT_AT_INFINITY
    )
    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_extra_participant(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    rng = random.Random(3030)
    random_participant = rng.choice(committee_indices)

    block = build_empty_block_for_next_slot(spec, state)
    # Exclude one signature even though the block claims the entire committee participated.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(committee_indices),
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            [index for index in committee_indices if index != random_participant],
        )
    )

    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_state_test
def test_sync_committee_rewards_nonduplicate_committee(spec, state):
    committee_indices = get_committee_indices(spec, state, duplicates=False)
    committee_size = len(committee_indices)
    committee_bits = [True] * committee_size
    active_validator_count = len(spec.get_active_validator_indices(state, spec.get_current_epoch(state)))

    # Preconditions of this test case
    assert active_validator_count > spec.SYNC_COMMITTEE_SIZE
    assert committee_size == len(set(committee_indices))

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_sync_committee_rewards_duplicate_committee_no_participation(spec, state):
    committee_indices = get_committee_indices(spec, state, duplicates=True)
    committee_size = len(committee_indices)
    committee_bits = [False] * committee_size
    active_validator_count = len(spec.get_active_validator_indices(state, spec.get_current_epoch(state)))

    # Preconditions of this test case
    assert active_validator_count < spec.SYNC_COMMITTEE_SIZE
    assert committee_size > len(set(committee_indices))

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_sync_committee_rewards_duplicate_committee_half_participation(spec, state):
    committee_indices = get_committee_indices(spec, state, duplicates=True)
    committee_size = len(committee_indices)
    committee_bits = [True] * (committee_size // 2) + [False] * (committee_size // 2)
    assert len(committee_bits) == committee_size
    active_validator_count = len(spec.get_active_validator_indices(state, spec.get_current_epoch(state)))

    # Preconditions of this test case
    assert active_validator_count < spec.SYNC_COMMITTEE_SIZE
    assert committee_size > len(set(committee_indices))

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_sync_committee_rewards_duplicate_committee_full_participation(spec, state):
    committee_indices = get_committee_indices(spec, state, duplicates=True)
    committee_size = len(committee_indices)
    committee_bits = [True] * committee_size
    active_validator_count = len(spec.get_active_validator_indices(state, spec.get_current_epoch(state)))

    # Preconditions of this test case
    assert active_validator_count < spec.SYNC_COMMITTEE_SIZE
    assert committee_size > len(set(committee_indices))

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@spec_state_test
@always_bls
def test_sync_committee_rewards_not_full_participants(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    rng = random.Random(1010)
    committee_bits = [rng.choice([True, False]) for _ in committee_indices]

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@spec_state_test
@always_bls
def test_sync_committee_rewards_empty_participants(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    committee_bits = [False for _ in committee_indices]

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_past_block(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)

    for _ in range(2):
        # NOTE: need to transition twice to move beyond the degenerate case at genesis
        block = build_empty_block_for_next_slot(spec, state)
        # Valid sync committee signature here...
        block.body.sync_aggregate = spec.SyncAggregate(
            sync_committee_bits=[True] * len(committee_indices),
            sync_committee_signature=compute_aggregate_sync_committee_signature(
                spec,
                state,
                block.slot - 1,
                committee_indices,
            )
        )

        state_transition_and_sign_block(spec, state, block)

    invalid_block = build_empty_block_for_next_slot(spec, state)
    # Invalid signature from a slot other than the previous
    invalid_block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(committee_indices),
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            invalid_block.slot - 2,
            committee_indices,
        )
    )

    yield from run_sync_committee_processing(spec, state, invalid_block, expect_exception=True)


@with_altair_and_later
@with_presets([MINIMAL], reason="to produce different committee sets")
@spec_state_test
@always_bls
def test_invalid_signature_previous_committee(spec, state):
    # NOTE: the `state` provided is at genesis and the process to select
    # sync committees currently returns the same committee for the first and second
    # periods at genesis.
    # To get a distinct committee so we can generate an "old" signature, we need to advance
    # 2 EPOCHS_PER_SYNC_COMMITTEE_PERIOD periods.
    current_epoch = spec.get_current_epoch(state)
    old_sync_committee = state.next_sync_committee

    epoch_in_future_sync_commitee_period = current_epoch + 2 * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    slot_in_future_sync_committee_period = epoch_in_future_sync_commitee_period * spec.SLOTS_PER_EPOCH
    transition_to(spec, state, slot_in_future_sync_committee_period)

    # Use the previous sync committee to produce the signature.
    # Ensure that the pubkey sets are different.
    assert set(old_sync_committee.pubkeys) != set(state.current_sync_committee.pubkeys)
    committee_indices = compute_committee_indices(spec, state, old_sync_committee)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(committee_indices),
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            committee_indices,
        )
    )

    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_altair_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="too slow")
def test_valid_signature_future_committee(spec, state):
    # NOTE: the `state` provided is at genesis and the process to select
    # sync committees currently returns the same committee for the first and second
    # periods at genesis.
    # To get a distinct committee so we can generate an "old" signature, we need to advance
    # 2 EPOCHS_PER_SYNC_COMMITTEE_PERIOD periods.
    current_epoch = spec.get_current_epoch(state)
    old_current_sync_committee = state.current_sync_committee
    old_next_sync_committee = state.next_sync_committee

    epoch_in_future_sync_committee_period = current_epoch + 2 * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    slot_in_future_sync_committee_period = epoch_in_future_sync_committee_period * spec.SLOTS_PER_EPOCH
    transition_to(spec, state, slot_in_future_sync_committee_period)

    sync_committee = state.current_sync_committee
    next_sync_committee = state.next_sync_committee

    assert next_sync_committee != sync_committee
    assert sync_committee != old_current_sync_committee
    assert sync_committee != old_next_sync_committee

    committee_indices = compute_committee_indices(spec, state, sync_committee)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(committee_indices),
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            committee_indices,
        )
    )

    yield from run_sync_committee_processing(spec, state, block)


@with_altair_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="prefer short search to find matching proposer")
def test_proposer_in_committee_without_participation(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)

    # NOTE: seem to reliably be getting a matching proposer in the first epoch w/ ``MINIMAL`` preset.
    for _ in range(spec.SLOTS_PER_EPOCH):
        block = build_empty_block_for_next_slot(spec, state)
        proposer_index = block.proposer_index
        proposer_pubkey = state.validators[proposer_index].pubkey
        proposer_is_in_sync_committee = proposer_pubkey in state.current_sync_committee.pubkeys
        if proposer_is_in_sync_committee:
            participation = [index != proposer_index for index in committee_indices]
            participants = [index for index in committee_indices if index != proposer_index]
        else:
            participation = [True for _ in committee_indices]
            participants = committee_indices
        # Valid sync committee signature here...
        block.body.sync_aggregate = spec.SyncAggregate(
            sync_committee_bits=participation,
            sync_committee_signature=compute_aggregate_sync_committee_signature(
                spec,
                state,
                block.slot - 1,
                participants,
            )
        )

        if proposer_is_in_sync_committee:
            assert state.validators[block.proposer_index].pubkey in state.current_sync_committee.pubkeys
            yield from run_sync_committee_processing(spec, state, block)
            break
        else:
            state_transition_and_sign_block(spec, state, block)
    else:
        raise AssertionError("failed to find a proposer in the sync committee set; check test setup")


@with_altair_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="prefer short search to find matching proposer")
def test_proposer_in_committee_with_participation(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    participation = [True for _ in committee_indices]

    # NOTE: seem to reliably be getting a matching proposer in the first epoch w/ ``MINIMAL`` preset.
    for _ in range(spec.SLOTS_PER_EPOCH):
        block = build_empty_block_for_next_slot(spec, state)
        proposer_index = block.proposer_index
        proposer_pubkey = state.validators[proposer_index].pubkey
        proposer_is_in_sync_committee = proposer_pubkey in state.current_sync_committee.pubkeys

        # Valid sync committee signature here...
        block.body.sync_aggregate = spec.SyncAggregate(
            sync_committee_bits=participation,
            sync_committee_signature=compute_aggregate_sync_committee_signature(
                spec,
                state,
                block.slot - 1,
                committee_indices,
            )
        )

        if proposer_is_in_sync_committee:
            assert state.validators[block.proposer_index].pubkey in state.current_sync_committee.pubkeys
            yield from run_sync_committee_processing(spec, state, block)
            return
        else:
            state_transition_and_sign_block(spec, state, block)
    raise AssertionError("failed to find a proposer in the sync committee set; check test setup")
