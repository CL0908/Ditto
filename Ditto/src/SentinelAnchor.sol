// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @notice Anchors Merkle roots of Sentinel IoT alert logs on-chain for tamper-evident proof.
contract SentinelAnchor {
    struct Checkpoint {
        bytes32 merkleRoot;
        uint256 timestamp;
        uint256 alertCount;
    }

    mapping(address => Checkpoint[]) private checkpoints;

    event Anchored(
        address indexed submitter,
        bytes32 merkleRoot,
        uint256 timestamp,
        uint256 alertCount,
        uint256 index
    );

    /// @notice Records a new checkpoint anchoring `merkleRoot` for `alertCount` alerts.
    /// @return index The index of the newly created checkpoint for msg.sender.
    function anchor(bytes32 merkleRoot, uint256 alertCount) external returns (uint256 index) {
        index = checkpoints[msg.sender].length;
        checkpoints[msg.sender].push(Checkpoint({
            merkleRoot: merkleRoot,
            timestamp: block.timestamp,
            alertCount: alertCount
        }));

        emit Anchored(msg.sender, merkleRoot, block.timestamp, alertCount, index);
    }

    /// @notice Number of checkpoints anchored by `submitter`.
    function checkpointCount(address submitter) external view returns (uint256) {
        return checkpoints[submitter].length;
    }

    /// @notice Details of a specific checkpoint anchored by `submitter`.
    function getCheckpoint(address submitter, uint256 index)
        external
        view
        returns (bytes32 merkleRoot, uint256 timestamp, uint256 alertCount)
    {
        Checkpoint storage checkpoint = checkpoints[submitter][index];
        return (checkpoint.merkleRoot, checkpoint.timestamp, checkpoint.alertCount);
    }
}
