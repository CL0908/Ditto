# Foundry Injective Starter Template

<div align="center">
  <p>Minimal Foundry starter for compiling, testing, deploying, verifying, and interacting with a Counter contract on Injective EVM.</p>
  <p>
    <strong>Stack:</strong>Solidity · Foundry · Injective EVM · Blockscout
  </p>
</div>

## Quick Start

- On GitHub, press the "Use this template" button.
- In the dropdown, select "Create new repository"
- Fill in the form, then press the "Create repository"
- You should now have a copy of the template repo in your own Github account or organisation
- Click on the "<> Code" button
- In the dropdown, select the "Local" tab, then copy the git URL

```bash
git clone https://github.com/${YOUR_GITHUB}/foundry-injective-template.git foundry-injective-template
cd foundry-injective-template
cp .env.example .env
make compile         # compile contract
make test            # run local (simulated EVM) tests
make deploy          # deploy contract to Injective Testnet
make verify          # verify deployed contract on Injective Testnet Blockscout
make interact-read   # query with deployed contract
make interact-write  # transact with deployed contract
```

Update `.env` (see the "Configuration" section for more details):
- Add your private key, before running the deploy command.
- Add deployed contract address, before running verify or the interact commands.

## What's Included

### Smart Contract Workflow

- [x] **Compile workflow**: `make compile` builds the Counter contract.
- [x] **Test workflow**: `make test` runs the test suite for Counter.
- [x] **Deploy workflow**: `make deploy` deploys Counter to Injective EVM Testnet.
- [x] **Verify workflow**: `make verify` verifies the deployed contract on Blockscout.
- [x] **Interact workflow**: `make interact-read` and `make interact-write` demonstrate read and write contract calls on the Counter contract.

### Project Foundation

- [x] **Counter contract**: Canonical hello-world smart contract example for extending the starter.
- [x] **Minimal Foundry config**: `foundry.toml` keeps the repo bare while supporting the required workflows.
- [x] **Env placeholders**: `.env.example` avoids hardcoded user-specific values.

## Project Structure

```text
├── src/
│   └── Counter.sol   # Canonical hello-world smart contract
├── test/
│   └── Counter.t.sol # Matching Foundry test suite
├── .env.example      # RPC, key, verifier, and contract placeholders
├── foundry.toml      # Foundry configuration and Injective RPC alias
├── Makefile          # Helper targets for compile, test, deploy, verify, and interact
└── README.md
```

## Configuration

Copy `.env.example` to `.env` and replace placeholders before using the networked workflows.

- `PRIVATE_KEY` is required for `make deploy` and `make interact-write`.
- `CONTRACT_ADDRESS` is required for `make verify`, `make interact-read`, and `make interact-write`.

## Author

[Brendan Graetz](https://blog.bguiz.com/)

## License

MIT
