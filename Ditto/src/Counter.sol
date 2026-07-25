// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

contract Counter {
    uint256 public value;

    function increment(uint256 amount) external {
        value += amount;
    }
}
