"""
Bitcoin Blockchain CLI Visualizer
==================================

This module provides a rich, colorful command-line visualization of the
blockchain state using the ``rich`` library.  It is intended as an
educational tool that makes it easy to inspect blocks, transactions, the
UTXO set, the mempool, and the overall chain structure -- including forks.

The visualizer does not modify any blockchain state; it is purely a
read-only presentation layer.

Features:

- **Chain table**: A tabular view of the blockchain with columns for height,
  hash, previous hash, nonce, transaction count, and timestamp.

- **Block detail view**: Full information about a single block, including
  its header fields and a summary of each transaction.

- **Fork tree**: A tree diagram showing the full block-tree structure with
  branches where forks exist.  This is especially useful for understanding
  chain reorganizations.

- **UTXO summary**: Overview of the unspent transaction output set, optionally
  filtered by address.

- **Mempool view**: Table of pending unconfirmed transactions waiting to be
  included in a block.

- **Chain info**: High-level statistics about the blockchain (height, number
  of tips, difficulty, total transactions, UTXO count).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

try:
    from rich.console import Console
    from rich.table import Table
    from rich.tree import Tree
    from rich.panel import Panel
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

if TYPE_CHECKING:
    from src.core.blockchain import Blockchain
    from src.core.block import Block

logger = logging.getLogger(__name__)


def _format_timestamp(ts: int) -> str:
    """Convert a Unix timestamp to a human-readable UTC string."""
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError, OverflowError):
        return str(ts)


def _truncate_hash(h: str, length: int = 16) -> str:
    """Return the first *length* characters of a hex hash."""
    if h is None:
        return "None"
    return h[:length]


class BlockchainVisualizer:
    """
    Rich CLI visualizer for the Bitcoin blockchain.

    Provides multiple views into the blockchain state: tabular chain
    display, detailed block inspection, fork tree diagrams, UTXO
    summaries, and mempool listings.

    Attributes:
        blockchain: Reference to the Blockchain instance to visualize.
        console: A ``rich.console.Console`` used for all output.
    """

    def __init__(self, blockchain: "Blockchain") -> None:
        """
        Initialize the visualizer.

        Args:
            blockchain: The Blockchain instance to visualize.

        Raises:
            ImportError: If the ``rich`` library is not installed.
        """
        if not RICH_AVAILABLE:
            raise ImportError(
                "The 'rich' library is required for visualization. "
                "Install it with: pip install rich"
            )
        self.blockchain = blockchain
        self.console = Console()

    # ------------------------------------------------------------------
    # Chain table
    # ------------------------------------------------------------------

    def print_chain(
        self,
        start_height: int = 0,
        end_height: int | None = None,
        max_rows: int = 50,
    ) -> None:
        """
        Print the blockchain as a rich table.

        Displays one row per block on the best chain, with columns for
        height, hash, previous hash, nonce, transaction count, and
        timestamp.

        Args:
            start_height: First block height to display (inclusive).
            end_height: Last block height to display (inclusive).  Defaults
                to the chain tip.
            max_rows: Maximum number of rows to render.
        """
        chain = self.blockchain.get_chain()
        if not chain:
            self.console.print("[yellow]Blockchain is empty.[/yellow]")
            return

        if end_height is None:
            end_height = self.blockchain.get_chain_height()

        table = Table(
            title="Blockchain",
            show_header=True,
            header_style="bold cyan",
            border_style="blue",
        )
        table.add_column("Height", style="bold white", justify="right")
        table.add_column("Hash", style="green")
        table.add_column("Prev Hash", style="dim green")
        table.add_column("Nonce", justify="right", style="yellow")
        table.add_column("Txs", justify="right", style="magenta")
        table.add_column("Timestamp", style="dim white")

        rows_added = 0
        for block in chain:
            height = block.height if block.height is not None else "?"
            if isinstance(height, int):
                if height < start_height or height > end_height:
                    continue

            if rows_added >= max_rows:
                table.add_row("...", "...", "...", "...", "...", "...")
                break

            table.add_row(
                str(height),
                _truncate_hash(block.header.hash),
                _truncate_hash(block.header.previous_block_hash),
                str(block.header.nonce),
                str(len(block.transactions)),
                _format_timestamp(block.header.timestamp),
            )
            rows_added += 1

        self.console.print(table)

    # ------------------------------------------------------------------
    # Block detail view
    # ------------------------------------------------------------------

    def print_block_details(self, block_hash_or_height) -> None:
        """
        Print detailed information about a single block.

        Accepts either a block hash (string) or a height (integer).

        Args:
            block_hash_or_height: Block hash (str) or height (int).
        """
        block = self._resolve_block(block_hash_or_height)
        if block is None:
            self.console.print(
                f"[red]Block not found: {block_hash_or_height}[/red]"
            )
            return

        header = block.header
        height = block.height if block.height is not None else "unknown"

        # Header information panel
        info_lines = [
            f"[bold]Height:[/bold]          {height}",
            f"[bold]Hash:[/bold]            {header.hash}",
            f"[bold]Previous Hash:[/bold]   {header.previous_block_hash}",
            f"[bold]Merkle Root:[/bold]     {header.merkle_root}",
            f"[bold]Timestamp:[/bold]       {_format_timestamp(header.timestamp)} ({header.timestamp})",
            f"[bold]Nonce:[/bold]           {header.nonce}",
            f"[bold]Difficulty Bits:[/bold] {header.difficulty_bits:#010x}",
            f"[bold]Version:[/bold]         {header.version}",
        ]

        try:
            size = block.get_size()
            info_lines.append(f"[bold]Size:[/bold]            {size:,} bytes")
        except Exception:
            pass

        info_lines.append(f"[bold]Transactions:[/bold]    {len(block.transactions)}")

        panel = Panel(
            "\n".join(info_lines),
            title=f"Block {height}",
            border_style="cyan",
        )
        self.console.print(panel)

        # Transaction list
        if block.transactions:
            tx_table = Table(
                title="Transactions",
                show_header=True,
                header_style="bold magenta",
                border_style="magenta",
            )
            tx_table.add_column("#", justify="right", style="dim")
            tx_table.add_column("TXID", style="green")
            tx_table.add_column("Type", style="yellow")
            tx_table.add_column("Inputs", justify="right")
            tx_table.add_column("Outputs", justify="right")
            tx_table.add_column("Output Value", justify="right", style="cyan")

            for i, tx in enumerate(block.transactions):
                tx_type = "coinbase" if tx.is_coinbase() else "regular"
                total_output = sum(out.value for out in tx.outputs)
                # Display value in BTC for readability
                btc_value = total_output / 100_000_000

                tx_table.add_row(
                    str(i),
                    _truncate_hash(tx.txid),
                    tx_type,
                    str(len(tx.inputs)),
                    str(len(tx.outputs)),
                    f"{btc_value:.8f} BTC",
                )

            self.console.print(tx_table)

    # ------------------------------------------------------------------
    # Fork tree
    # ------------------------------------------------------------------

    def print_fork_tree(self) -> None:
        """
        Display the blockchain structure as a tree diagram.

        The tree starts at the genesis block and branches wherever forks
        exist.  The best chain tip is highlighted.  This view makes it
        easy to visualize competing branches and understand reorgs.
        """
        if not self.blockchain.blocks:
            self.console.print("[yellow]Blockchain is empty.[/yellow]")
            return

        # Find the genesis block (height 0)
        genesis_hashes = self.blockchain.block_height_index.get(0, [])
        if not genesis_hashes:
            self.console.print("[red]No genesis block found.[/red]")
            return

        genesis_hash = genesis_hashes[0]
        genesis_block = self.blockchain.blocks.get(genesis_hash)
        if genesis_block is None:
            self.console.print("[red]Genesis block missing.[/red]")
            return

        # Build a children map: parent_hash -> list of child hashes
        children_map: dict[str, list[str]] = {}
        for block_hash, block in self.blockchain.blocks.items():
            parent = block.header.previous_block_hash
            if parent not in children_map:
                children_map[parent] = []
            children_map[parent].append(block_hash)

        # Build tree recursively
        best_tip = self.blockchain.best_chain_tip

        def _label(block_hash: str) -> str:
            blk = self.blockchain.blocks.get(block_hash)
            if blk is None:
                return f"[red]{_truncate_hash(block_hash)}[/red]"
            h = blk.height if blk.height is not None else "?"
            is_tip = block_hash == best_tip
            tip_marker = " [bold green]<-- BEST TIP[/bold green]" if is_tip else ""
            is_chain_tip = block_hash in self.blockchain.chain_tips and not is_tip
            fork_marker = " [yellow](tip)[/yellow]" if is_chain_tip else ""
            return (
                f"[bold]H{h}[/bold] {_truncate_hash(block_hash)} "
                f"[dim]({len(blk.transactions)} txs)[/dim]"
                f"{tip_marker}{fork_marker}"
            )

        tree = Tree(
            _label(genesis_hash),
            guide_style="blue",
        )

        def _build_tree(parent_hash: str, parent_node: Tree) -> None:
            child_hashes = children_map.get(parent_hash, [])
            for child_hash in child_hashes:
                child_node = parent_node.add(_label(child_hash))
                _build_tree(child_hash, child_node)

        _build_tree(genesis_hash, tree)

        self.console.print(Panel(tree, title="Blockchain Fork Tree", border_style="blue"))

    # ------------------------------------------------------------------
    # UTXO summary
    # ------------------------------------------------------------------

    def print_utxo_summary(self, address: str | None = None) -> None:
        """
        Print a summary of the UTXO set.

        If *address* is provided, only UTXOs belonging to that address
        are shown. Otherwise, aggregate statistics are displayed.

        Args:
            address: Optional address (pubkey_script) to filter by.
        """
        utxo_set = self.blockchain.utxo_set

        if address is not None:
            # Show UTXOs for a specific address
            try:
                utxos = utxo_set.get_utxos_for_address(address)
                balance = utxo_set.get_balance(address)
            except Exception:
                utxos = []
                balance = 0

            btc_balance = balance / 100_000_000

            self.console.print(
                Panel(
                    f"[bold]Address:[/bold] {address}\n"
                    f"[bold]Balance:[/bold] {btc_balance:.8f} BTC ({balance:,} satoshis)\n"
                    f"[bold]UTXOs:[/bold]   {len(utxos)}",
                    title="Address UTXO Summary",
                    border_style="green",
                )
            )

            if utxos:
                table = Table(
                    show_header=True,
                    header_style="bold green",
                    border_style="green",
                )
                table.add_column("TXID", style="green")
                table.add_column("Index", justify="right")
                table.add_column("Value (sat)", justify="right", style="cyan")
                table.add_column("Value (BTC)", justify="right", style="bold cyan")
                table.add_column("Height", justify="right")
                table.add_column("Coinbase", justify="center")

                for utxo_info in utxos:
                    if isinstance(utxo_info, dict):
                        txid = utxo_info.get("txid", "?")
                        index = utxo_info.get("index", "?")
                        value = utxo_info.get("value", 0)
                        blk_height = utxo_info.get("block_height", "?")
                        is_cb = utxo_info.get("is_coinbase", False)
                    elif isinstance(utxo_info, tuple) and len(utxo_info) >= 3:
                        txid, index = utxo_info[0], utxo_info[1]
                        entry = utxo_info[2]
                        value = getattr(entry, "value", 0)
                        blk_height = getattr(entry, "block_height", "?")
                        is_cb = getattr(entry, "is_coinbase", False)
                    else:
                        continue

                    table.add_row(
                        _truncate_hash(str(txid)),
                        str(index),
                        f"{value:,}",
                        f"{value / 100_000_000:.8f}",
                        str(blk_height),
                        "yes" if is_cb else "no",
                    )

                self.console.print(table)
        else:
            # General UTXO set summary
            total_utxos = 0
            total_value = 0
            try:
                utxo_dict = utxo_set.to_dict()
                utxo_entries = utxo_dict.get("utxos", utxo_dict)
                if isinstance(utxo_entries, dict):
                    total_utxos = len(utxo_entries)
                    for entry in utxo_entries.values():
                        if isinstance(entry, dict):
                            total_value += entry.get("value", 0)
            except Exception:
                pass

            btc_total = total_value / 100_000_000 if total_value else 0

            self.console.print(
                Panel(
                    f"[bold]Total UTXOs:[/bold]     {total_utxos:,}\n"
                    f"[bold]Total Value:[/bold]     {btc_total:.8f} BTC ({total_value:,} satoshis)",
                    title="UTXO Set Summary",
                    border_style="green",
                )
            )

    # ------------------------------------------------------------------
    # Mempool view
    # ------------------------------------------------------------------

    def print_mempool(self) -> None:
        """
        Print the contents of the transaction mempool as a table.

        Transactions are shown in fee-rate priority order (highest first).
        """
        mempool = self.blockchain.mempool

        if mempool.size == 0:
            self.console.print("[yellow]Mempool is empty.[/yellow]")
            return

        self.console.print(
            Panel(
                f"[bold]Pending Transactions:[/bold] {mempool.size}",
                title="Mempool",
                border_style="yellow",
            )
        )

        table = Table(
            show_header=True,
            header_style="bold yellow",
            border_style="yellow",
        )
        table.add_column("#", justify="right", style="dim")
        table.add_column("TXID", style="green")
        table.add_column("Inputs", justify="right")
        table.add_column("Outputs", justify="right")
        table.add_column("Output Value (sat)", justify="right", style="cyan")
        table.add_column("Fee Rate", justify="right", style="magenta")

        for i, (fee_rate, txid) in enumerate(mempool._fee_index):
            tx = mempool.transactions.get(txid)
            if tx is None:
                continue
            total_output = sum(out.value for out in tx.outputs)
            table.add_row(
                str(i + 1),
                _truncate_hash(txid),
                str(len(tx.inputs)),
                str(len(tx.outputs)),
                f"{total_output:,}",
                f"{fee_rate:.4f}",
            )

        self.console.print(table)

    # ------------------------------------------------------------------
    # Chain info summary
    # ------------------------------------------------------------------

    def print_chain_info(self) -> None:
        """
        Print high-level statistics about the blockchain.

        Includes chain height, number of tips, current difficulty,
        total transaction count, and UTXO set size.
        """
        bc = self.blockchain

        height = bc.get_chain_height()
        num_blocks = len(bc.blocks)
        num_tips = len(bc.chain_tips)
        difficulty_bits = bc._difficulty_bits

        # Count total transactions across all blocks
        total_txs = sum(len(blk.transactions) for blk in bc.blocks.values())

        # UTXO count
        try:
            utxo_dict = bc.utxo_set.to_dict()
            utxo_entries = utxo_dict.get("utxos", utxo_dict)
            utxo_count = len(utxo_entries) if isinstance(utxo_entries, dict) else 0
        except Exception:
            utxo_count = 0

        mempool_size = bc.mempool.size

        best_tip_hash = bc.best_chain_tip or "none"

        info = (
            f"[bold]Chain Height:[/bold]      {height}\n"
            f"[bold]Total Blocks:[/bold]      {num_blocks}\n"
            f"[bold]Chain Tips:[/bold]        {num_tips}\n"
            f"[bold]Best Tip:[/bold]          {_truncate_hash(best_tip_hash)}\n"
            f"[bold]Difficulty Bits:[/bold]   {difficulty_bits:#010x}\n"
            f"[bold]Total Transactions:[/bold] {total_txs:,}\n"
            f"[bold]UTXO Count:[/bold]        {utxo_count:,}\n"
            f"[bold]Mempool Size:[/bold]      {mempool_size}\n"
            f"[bold]Mode:[/bold]              {'Development' if bc.development_mode else 'Production'}"
        )

        self.console.print(Panel(info, title="Blockchain Info", border_style="cyan"))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_block(self, block_hash_or_height) -> "Block | None":
        """
        Resolve a block from either a hash string or a height integer.

        Args:
            block_hash_or_height: Block hash (str) or height (int).

        Returns:
            The Block object, or None if not found.
        """
        if isinstance(block_hash_or_height, int):
            return self.blockchain.get_block_by_height(block_hash_or_height)
        elif isinstance(block_hash_or_height, str):
            # Try as a full hash first
            block = self.blockchain.get_block(block_hash_or_height)
            if block is not None:
                return block
            # Try as a height string
            try:
                height = int(block_hash_or_height)
                return self.blockchain.get_block_by_height(height)
            except ValueError:
                pass
            # Try as a partial hash prefix
            for block_hash, block in self.blockchain.blocks.items():
                if block_hash.startswith(block_hash_or_height):
                    return block
        return None
