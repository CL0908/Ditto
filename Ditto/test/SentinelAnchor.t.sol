// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {SentinelAnchor} from "../src/SentinelAnchor.sol";

contract SentinelAnchorTest {
    function test_InitialCheckpointCountIsZero() public {
        SentinelAnchor sentinel = new SentinelAnchor();
        assert(sentinel.checkpointCount(address(this)) == 0);
    }

    function test_AnchorStoresCheckpoint() public {
        SentinelAnchor sentinel = new SentinelAnchor();
        bytes32 root = keccak256("merkle-root-1");

        uint256 index = sentinel.anchor(root, 5);
        assert(index == 0);
        assert(sentinel.checkpointCount(address(this)) == 1);

        (bytes32 storedRoot, uint256 timestamp, uint256 alertCount) =
            sentinel.getCheckpoint(address(this), 0);
        assert(storedRoot == root);
        assert(timestamp == block.timestamp);
        assert(alertCount == 5);
    }

    function test_MultipleAnchorsIncrementIndex() public {
        SentinelAnchor sentinel = new SentinelAnchor();
        bytes32 rootA = keccak256("root-a");
        bytes32 rootB = keccak256("root-b");

        sentinel.anchor(rootA, 3);
        uint256 indexB = sentinel.anchor(rootB, 7);

        assert(indexB == 1);
        assert(sentinel.checkpointCount(address(this)) == 2);

        (bytes32 storedRootB,, uint256 alertCountB) = sentinel.getCheckpoint(address(this), 1);
        assert(storedRootB == rootB);
        assert(alertCountB == 7);
    }

    function test_CheckpointsAreIsolatedPerSubmitter() public {
        SentinelAnchor sentinel = new SentinelAnchor();
        sentinel.anchor(keccak256("only-mine"), 1);

        assert(sentinel.checkpointCount(address(this)) == 1);
        assert(sentinel.checkpointCount(address(0xBEEF)) == 0);
    }

    function test_RevertsOnOutOfBoundsIndex() public {
        SentinelAnchor sentinel = new SentinelAnchor();
        sentinel.anchor(keccak256("root"), 1);

        try sentinel.getCheckpoint(address(this), 1) returns (bytes32, uint256, uint256) {
            assert(false);
        } catch {
            // expected: index out of bounds
        }
    }
}
