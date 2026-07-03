// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Counter} from "../src/Counter.sol";

contract CounterTest {
    function test_InitialValueIsZero() public {
        Counter counter = new Counter();
        assert(counter.value() == 0);
    }

    function test_IncrementFromZero() public {
        Counter counter = new Counter();
        counter.increment(100);
        assert(counter.value() == 100);
    }

    function test_IncrementFromNonZero() public {
        Counter counter = new Counter();
        counter.increment(100);
        counter.increment(23);
        assert(counter.value() == 123);
    }
}
