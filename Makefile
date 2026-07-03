-include .env
export

RPC_URL ?= https://injectiveevm-testnet-rpc.polkachu.com
VERIFIER_URL ?= https://testnet.blockscout-api.injective.network/api/
GAS_PRICE ?= 160000000
GAS_LIMIT ?= 2000000
INCREMENT_AMOUNT ?= 1

.PHONY: help compile test deploy verify interact-read interact-write

help:
	@printf "make compile         Compile the contract\n"
	@printf "make test            Run the test suite\n"
	@printf "make deploy          Deploy contract to Injective EVM\n"
	@printf "make verify          Verify contract on Blockscout\n"
	@printf "make interact-read   Query contract\n"
	@printf "make interact-write  Transact to update contract state\n"

compile:
	forge build

test:
	FOUNDRY_OFFLINE=true forge test

deploy:
	@test -n "$(PRIVATE_KEY)" || (echo "Set PRIVATE_KEY in .env or your shell." && exit 1)
	forge create src/Counter.sol:Counter \
		--rpc-url "$(RPC_URL)" \
		--private-key "$(PRIVATE_KEY)" \
		--legacy \
		--gas-price "$(GAS_PRICE)" \
		--gas-limit "$(GAS_LIMIT)" \
		--broadcast

verify:
	@test -n "$(CONTRACT_ADDRESS)" || (echo "Set CONTRACT_ADDRESS in .env or your shell." && exit 1)
	forge verify-contract \
		--rpc-url "$(RPC_URL)" \
		--verifier blockscout \
		--verifier-url "$(VERIFIER_URL)" \
		"$(CONTRACT_ADDRESS)" \
		src/Counter.sol:Counter

interact-read:
	@test -n "$(CONTRACT_ADDRESS)" || (echo "Set CONTRACT_ADDRESS in .env or your shell." && exit 1)
	cast call \
		--rpc-url "$(RPC_URL)" \
		"$(CONTRACT_ADDRESS)" \
		"value()(uint256)"

interact-write:
	@test -n "$(PRIVATE_KEY)" || (echo "Set PRIVATE_KEY in .env or your shell." && exit 1)
	@test -n "$(CONTRACT_ADDRESS)" || (echo "Set CONTRACT_ADDRESS in .env or your shell." && exit 1)
	cast send \
		--rpc-url "$(RPC_URL)" \
		--private-key "$(PRIVATE_KEY)" \
		--legacy \
		--gas-price "$(GAS_PRICE)" \
		--gas-limit "$(GAS_LIMIT)" \
		"$(CONTRACT_ADDRESS)" \
		"increment(uint256)" \
		"$(INCREMENT_AMOUNT)"
