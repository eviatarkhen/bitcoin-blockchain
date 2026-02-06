"""
Bitcoin Wallet Implementation
==============================

This module implements a simplified Bitcoin wallet that manages key pairs,
tracks balances via the UTXO set, and creates/signs transactions.

A Bitcoin wallet is conceptually a keychain -- it holds the private keys that
control bitcoins. The bitcoins themselves are recorded on the blockchain as
unspent transaction outputs (UTXOs). The wallet's balance is the sum of all
UTXOs that can be spent by the wallet's private keys.

Key responsibilities of a wallet:
1. **Key Management** (Tasks 6.1, 6.6): Generate, store, import, and export
   private/public key pairs and their derived Bitcoin addresses.
2. **Balance Tracking** (Task 6.2): Query the blockchain's UTXO set to
   determine the total balance across all wallet addresses.
3. **Coin Selection** (Task 6.3): Choose which UTXOs to spend when creating
   a transaction, balancing efficiency and privacy.
4. **Transaction Creation** (Task 6.4): Build unsigned transactions with
   the correct inputs, outputs, and change.
5. **Transaction Signing** (Task 6.5): Sign transaction inputs with the
   appropriate private keys to authorize spending.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.crypto.keys import KeyPair, PrivateKey, PublicKey
from src.core.transaction import Transaction, TransactionInput, TransactionOutput

if TYPE_CHECKING:
    from src.core.blockchain import Blockchain
    from src.core.utxo import UTXOEntry


class Wallet:
    """
    A Bitcoin wallet that manages keys and creates signed transactions.

    The wallet maintains a collection of key pairs (private key + public key +
    address). When connected to a blockchain, it can query UTXO balances and
    create transactions that spend those UTXOs.

    Attributes:
        _keypairs: Dictionary mapping Bitcoin addresses to their KeyPair objects.
        _blockchain: Optional reference to a Blockchain for UTXO queries.
        name: Human-readable name for this wallet (e.g., "Alice", "Bob").
    """

    def __init__(self, blockchain: Optional["Blockchain"] = None, name: str = "default"):
        """
        Initialize a wallet with an optional blockchain reference.

        Args:
            blockchain: Optional Blockchain instance for UTXO lookups.
                        Can be set later or left None for offline key management.
            name: A human-readable identifier for this wallet.
        """
        self._keypairs: dict[str, KeyPair] = {}
        self._blockchain = blockchain
        self.name = name

    # =========================================================================
    # Key Management (Task 6.1)
    # =========================================================================

    def generate_address(self) -> str:
        """
        Generate a new key pair and return the derived Bitcoin address.

        This creates a fresh random private key, derives its public key and
        address, stores the key pair in the wallet, and returns the address.

        In a real Bitcoin wallet, users generate a new address for each
        transaction they receive to improve privacy (address reuse makes
        it easier to track a user's transaction history).

        Returns:
            The new Bitcoin address as a Base58Check-encoded string.
        """
        keypair = KeyPair.generate()
        self._keypairs[keypair.address] = keypair
        return keypair.address

    def get_addresses(self) -> list[str]:
        """
        Return all Bitcoin addresses managed by this wallet.

        Returns:
            A list of Base58Check-encoded address strings.
        """
        return list(self._keypairs.keys())

    def get_keypair(self, address: str) -> Optional[KeyPair]:
        """
        Retrieve the key pair for a specific address.

        Args:
            address: The Bitcoin address to look up.

        Returns:
            The KeyPair if the address belongs to this wallet, None otherwise.
        """
        return self._keypairs.get(address)

    def has_address(self, address: str) -> bool:
        """
        Check if this wallet controls the given address.

        Args:
            address: The Bitcoin address to check.

        Returns:
            True if this wallet has the private key for the address.
        """
        return address in self._keypairs

    # =========================================================================
    # Key Import/Export (Task 6.6)
    # =========================================================================

    def import_private_key(self, wif: str) -> str:
        """
        Import a private key in Wallet Import Format (WIF).

        WIF is a Base58Check-encoded representation of a private key that
        includes metadata about the network and compression. This method
        decodes the WIF string, derives the public key and address, and
        adds the key pair to the wallet.

        Args:
            wif: The WIF-encoded private key string (starts with '5', 'K',
                 'L' for mainnet, or 'c', '9' for testnet).

        Returns:
            The Bitcoin address derived from the imported key.

        Raises:
            ValueError: If the WIF string is invalid.
        """
        private_key = PrivateKey.from_wif(wif)
        public_key = private_key.public_key
        address = public_key.to_address(testnet=False)
        keypair = KeyPair(private_key, public_key, address)
        self._keypairs[address] = keypair
        return address

    def export_private_key(self, address: str) -> str:
        """
        Export the private key for an address in Wallet Import Format.

        Args:
            address: The Bitcoin address whose key to export.

        Returns:
            The WIF-encoded private key string.

        Raises:
            ValueError: If the address is not in this wallet.
        """
        keypair = self._keypairs.get(address)
        if keypair is None:
            raise ValueError(f"Address {address} not found in wallet '{self.name}'")
        return keypair.private_key.to_wif(compressed=True, testnet=False)

    # =========================================================================
    # Balance (Task 6.2)
    # =========================================================================

    def get_balance(self) -> int:
        """
        Calculate the total balance across all wallet addresses.

        The balance is the sum of all unspent transaction output (UTXO) values
        that are locked to any of this wallet's addresses.

        Returns:
            Total balance in satoshis (1 BTC = 100,000,000 satoshis).

        Raises:
            RuntimeError: If no blockchain is connected to this wallet.
        """
        if self._blockchain is None:
            raise RuntimeError(
                f"Wallet '{self.name}' is not connected to a blockchain. "
                "Set wallet._blockchain to query balances."
            )
        total = 0
        for address, kp in self._keypairs.items():
            pubkey_hash = kp.public_key.get_hash160()
            total += self._blockchain.utxo_set.get_balance(pubkey_hash)
        return total

    def get_utxos(self) -> list[tuple[str, int, "UTXOEntry"]]:
        """
        Retrieve all UTXOs controlled by this wallet.

        Queries the blockchain's UTXO set for every address in this wallet
        and returns a combined list of all spendable outputs.

        Returns:
            A list of (txid, output_index, UTXOEntry) tuples for all
            unspent outputs belonging to this wallet.

        Raises:
            RuntimeError: If no blockchain is connected.
        """
        if self._blockchain is None:
            raise RuntimeError(
                f"Wallet '{self.name}' is not connected to a blockchain."
            )
        utxos = []
        for address, kp in self._keypairs.items():
            pubkey_hash = kp.public_key.get_hash160()
            address_utxos = self._blockchain.utxo_set.get_utxos_for_address(pubkey_hash)
            utxos.extend(address_utxos)
        return utxos

    # =========================================================================
    # Coin Selection (Task 6.3)
    # =========================================================================

    def _select_coins(
        self, amount: int, fee: int
    ) -> tuple[list[tuple[str, int, "UTXOEntry", str]], int]:
        """
        Select UTXOs to cover the required amount plus fee.

        Uses a simple smallest-first strategy: sort all wallet UTXOs by value
        ascending, then accumulate until the target amount is met. This tends
        to consolidate small UTXOs, reducing the UTXO set size over time.

        Args:
            amount: The value to send in satoshis.
            fee: The transaction fee in satoshis.

        Returns:
            A tuple of:
            - selected: List of (txid, output_index, UTXOEntry, address) tuples
              for the selected UTXOs.
            - total_input_value: The sum of all selected UTXO values.

        Raises:
            ValueError: If the wallet doesn't have enough funds.
            RuntimeError: If no blockchain is connected.
        """
        target = amount + fee
        all_utxos_with_address = []

        if self._blockchain is None:
            raise RuntimeError(
                f"Wallet '{self.name}' is not connected to a blockchain."
            )

        # Gather all UTXOs with their owning address
        for address, kp in self._keypairs.items():
            pubkey_hash = kp.public_key.get_hash160()
            address_utxos = self._blockchain.utxo_set.get_utxos_for_address(pubkey_hash)
            for txid, idx, utxo_entry in address_utxos:
                all_utxos_with_address.append((txid, idx, utxo_entry, address))

        # Sort by value ascending (smallest first) for consolidation
        all_utxos_with_address.sort(key=lambda x: x[2].value)

        selected = []
        total_input_value = 0

        for txid, idx, utxo_entry, address in all_utxos_with_address:
            selected.append((txid, idx, utxo_entry, address))
            total_input_value += utxo_entry.value
            if total_input_value >= target:
                return selected, total_input_value

        raise ValueError(
            f"Insufficient funds in wallet '{self.name}': "
            f"need {target} satoshis (amount={amount} + fee={fee}), "
            f"have {total_input_value} satoshis"
        )

    # =========================================================================
    # Transaction Creation (Task 6.4)
    # =========================================================================

    def create_transaction(
        self, to_address: str, amount: int, fee: int = 10000
    ) -> Transaction:
        """
        Create an unsigned transaction sending `amount` satoshis to `to_address`.

        Steps:
        1. Select UTXOs (coins) to cover the amount + fee.
        2. Create transaction inputs referencing the selected UTXOs.
        3. Create an output paying the recipient.
        4. If there is change (input total > amount + fee), create a change
           output back to the first wallet address.
        5. Return the unsigned transaction (signature_script fields are empty).

        Args:
            to_address: The recipient's Bitcoin address (Base58Check).
            amount: The amount to send in satoshis.
            fee: The transaction fee in satoshis (default 10,000 = 0.0001 BTC).

        Returns:
            An unsigned Transaction ready for signing.

        Raises:
            ValueError: If insufficient funds or no addresses in wallet.
        """
        if not self._keypairs:
            raise ValueError(f"Wallet '{self.name}' has no addresses. Generate one first.")

        # Step 1: Select coins
        selected, total_input = self._select_coins(amount, fee)

        # Step 2: Create inputs
        inputs = []
        for txid, idx, utxo_entry, address in selected:
            tx_input = TransactionInput(
                previous_txid=txid,
                previous_output_index=idx,
                signature_script="",  # Will be filled during signing
                sequence=0xffffffff,
            )
            inputs.append(tx_input)

        # Step 3: Create output to recipient
        # Resolve the recipient address to a pubkey hash
        recipient_pubkey_hash = self._address_to_pubkey_hash(to_address)
        outputs = [
            TransactionOutput(value=amount, pubkey_script=recipient_pubkey_hash)
        ]

        # Step 4: Create change output if needed
        change = total_input - amount - fee
        if change > 0:
            # Send change back to the first wallet address
            change_address = list(self._keypairs.keys())[0]
            change_pubkey_hash = self._keypairs[change_address].public_key.get_hash160()
            outputs.append(
                TransactionOutput(value=change, pubkey_script=change_pubkey_hash)
            )

        # Step 5: Build and return the unsigned transaction
        tx = Transaction(
            version=1,
            inputs=inputs,
            outputs=outputs,
            locktime=0,
        )
        return tx

    # =========================================================================
    # Transaction Signing (Task 6.5)
    # =========================================================================

    def sign_transaction(self, tx: Transaction) -> Transaction:
        """
        Sign all inputs of a transaction with the appropriate private keys.

        For each input in the transaction:
        1. Determine which wallet address owns the UTXO being spent.
        2. Look up the private key for that address.
        3. Sign the serialized transaction with the private key.
        4. Set the input's signature_script to: hex(signature) + hex(pubkey).

        The signature_script format follows a simplified P2PKH scheme:
        the signature (DER-encoded) and compressed public key are concatenated
        as hex strings. In real Bitcoin, these would be pushed as separate
        script elements with length prefixes.

        Args:
            tx: The transaction to sign (modified in-place).

        Returns:
            The same transaction with signature_scripts populated.

        Raises:
            ValueError: If a UTXO's owning address cannot be found in the wallet.
        """
        # Get the serialized transaction data that will be signed.
        # In a full implementation, each input would sign a modified copy
        # of the transaction (SIGHASH). Here we use a simplified approach.
        tx_data = tx.serialize()

        for tx_input in tx.inputs:
            if tx_input.is_coinbase():
                continue

            # Find which address owns the UTXO referenced by this input
            owner_address = self._find_utxo_owner(
                tx_input.previous_txid,
                tx_input.previous_output_index,
            )

            if owner_address is None:
                raise ValueError(
                    f"Cannot sign input {tx_input.previous_txid}:"
                    f"{tx_input.previous_output_index} -- "
                    f"owning address not found in wallet '{self.name}'"
                )

            keypair = self._keypairs[owner_address]

            # Sign the transaction data
            signature = keypair.private_key.sign(tx_data)

            # Build signature_script: hex(signature) + hex(compressed_pubkey)
            sig_hex = signature.hex()
            pubkey_hex = keypair.public_key.to_hex(compressed=True)
            tx_input.signature_script = sig_hex + pubkey_hex

        # Invalidate cached txid since the transaction content changed
        tx._txid = None
        return tx

    def send(self, to_address: str, amount: int, fee: int = 10000) -> Transaction:
        """
        Create, sign, and broadcast a transaction in one step.

        This is a convenience method that:
        1. Creates an unsigned transaction via create_transaction().
        2. Signs it via sign_transaction().
        3. Submits it to the blockchain's mempool.

        Args:
            to_address: The recipient's Bitcoin address.
            amount: The amount to send in satoshis.
            fee: The transaction fee in satoshis.

        Returns:
            The signed Transaction that was added to the mempool.

        Raises:
            ValueError: If insufficient funds or signing fails.
            RuntimeError: If no blockchain is connected.
        """
        if self._blockchain is None:
            raise RuntimeError(
                f"Wallet '{self.name}' is not connected to a blockchain."
            )

        # Create and sign the transaction
        tx = self.create_transaction(to_address, amount, fee)
        tx = self.sign_transaction(tx)

        # Add to the mempool
        self._blockchain.mempool.add_transaction(tx, self._blockchain.utxo_set)

        return tx

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _find_utxo_owner(self, txid: str, output_index: int) -> Optional[str]:
        """
        Find which wallet address owns a specific UTXO.

        Looks up the UTXO in the blockchain's UTXO set and checks whether
        its pubkey_script matches any wallet address.

        Args:
            txid: The transaction ID of the UTXO.
            output_index: The output index within that transaction.

        Returns:
            The owning address string, or None if not found in this wallet.
        """
        if self._blockchain is None:
            return None

        utxo = self._blockchain.utxo_set.get_utxo(txid, output_index)
        if utxo is None:
            return None

        # The UTXO's pubkey_script is the hash160 of the owner's public key.
        # Match it against our wallet's key pairs.
        for address, keypair in self._keypairs.items():
            pubkey_hash = keypair.public_key.get_hash160()
            if pubkey_hash == utxo.pubkey_script:
                return address

        return None

    @staticmethod
    def _address_to_pubkey_hash(address: str) -> str:
        """
        Extract the public key hash from a Bitcoin address.

        A P2PKH Bitcoin address is Base58Check(version + hash160). This method
        decodes the address and returns the 20-byte hash160 as a hex string.

        Args:
            address: A Base58Check-encoded Bitcoin address.

        Returns:
            The 40-character hex string of the public key hash.
        """
        from src.utils.encoding import base58check_decode
        _version, payload = base58check_decode(address)
        return payload.hex()

    def __repr__(self) -> str:
        return (
            f"Wallet(name='{self.name}', "
            f"addresses={len(self._keypairs)})"
        )
