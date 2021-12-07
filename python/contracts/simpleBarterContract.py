import smartpy as sp


class SimpleBarterContract(sp.Contract):
    """This contract implements a simple barter contract where users can trade
    FA2 tokens and tez for other FA2 tokens.

    """

    TOKEN_TYPE = sp.TRecord(
        # The FA2 token contract address
        fa2=sp.TAddress,
        # The FA2 token id
        id=sp.TNat,
        # The number of editions to trade
        amount=sp.TNat).layout(("fa2", ("id", "amount")))

    TRADE_PROPOSAL_TYPE = sp.TRecord(
        # The first user involved in the trade
        user1=sp.TAddress,
        # The second user involved in the trade
        user2=sp.TAddress,
        # The first user tokens to trade
        tokens1=sp.TList(TOKEN_TYPE),
        # The second user tokens to trade
        tokens2=sp.TList(TOKEN_TYPE)).layout(
            ("user1", ("user2", ("tokens1", "tokens2"))))

    def __init__(self):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            trades=sp.TBigMap(sp.TNat, sp.TRecord(
                user1_accepted=sp.TBool,
                user2_accepted=sp.TBool,
                executed=sp.TBool,
                proposal=SimpleBarterContract.TRADE_PROPOSAL_TYPE)),
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            trades=sp.big_map(),
            counter=0)

    def check_is_user(self, trade_proposal):
        """Checks that the address that called the entry point is one of the
        users involved in the trade proposal.

        """
        sp.verify((sp.sender == trade_proposal.user1) | (sp.sender == trade_proposal.user2),
                  message="This can only be executed by one of the trade users")

    def check_no_tez_transfer(self):
        """Checks that no tez were transferred in the operation.

        """
        sp.verify(sp.amount == sp.tez(0),
                  message="The operation does not need tez transfers")

    def check_trade_not_executed(self, trade_id):
        """Checks that the trade id corresponds to an existing trade that has
        not been executed.

        """
        # Check that the trade id is present in the trades big map
        sp.verify(self.data.trades.contains(trade_id),
                  message="The provided trade id doesn't exist")

        # Check that the trade was not executed before
        sp.verify(~self.data.trades[trade_id].executed,
                  message="The trade was executed before")

    @sp.entry_point
    def propose_trade(self, trade_proposal):
        """Proposes a trade between two users.

        """
        # Define the input parameter data type
        sp.set_type(trade_proposal, SimpleBarterContract.TRADE_PROPOSAL_TYPE)

        # Check that the trade proposal comes from one of the users
        self.check_is_user(trade_proposal)

        # Check that the two involved users are not the same wallet
        sp.verify(trade_proposal.user1 != trade_proposal.user2,
                  message="The users involved in the trade need to be different")

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Loop over the first user token list
        sp.for token in trade_proposal.tokens1:
            # Check that at least one edition will be traded
            sp.verify(token.amount >= 0,
                      message="At least one token edition needs to be traded")

        # Loop over the second user token list
        sp.for token in trade_proposal.tokens2:
            # Check that at least one edition will be traded
            sp.verify(token.amount >= 0,
                      message="At least one token edition needs to be traded")

        # Update the trades bigmap with the new trade information
        self.data.trades[self.data.counter] = sp.record(
            user1_accepted=False,
            user2_accepted=False,
            executed=False,
            proposal=trade_proposal)

        # Increase the trades counter
        self.data.counter += 1

    @sp.entry_point
    def accept_trade(self, trade_id):
        """Accepts a trade.

        """
        # Define the input parameter data type
        sp.set_type(trade_id, sp.TNat)

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Check that the trade was not executed before
        self.check_trade_not_executed(trade_id)

        # Check that the sender is one of the trade users
        trade = self.data.trades[trade_id]
        self.check_is_user(trade.proposal)

        # Transfer the tokens to the barter account
        sp.if sp.sender == trade.proposal.user1:
            # Check that the user didn't accept the trade before
            sp.verify(~trade.user1_accepted,
                      message="The trade was accepted before")

            # Accept the trade
            trade.user1_accepted = True

            # Transfer all the editions to the barter account
            sp.for token in trade.proposal.tokens1:
                self.fa2_transfer(
                    fa2=token.fa2,
                    from_=sp.sender,
                    to_=sp.self_address,
                    token_id=token.id,
                    token_amount=token.amount)
        sp.else:
            # Check that the user didn't accept the trade before
            sp.verify(~trade.user2_accepted,
                      message="The trade was accepted before")

            # Accept the trade
            trade.user2_accepted = True

            # Transfer all the editions to the barter account
            sp.for token in trade.proposal.tokens2:
                self.fa2_transfer(
                    fa2=token.fa2,
                    from_=sp.sender,
                    to_=sp.self_address,
                    token_id=token.id,
                    token_amount=token.amount)

    @sp.entry_point
    def cancel_trade(self, trade_id):
        """Cancels an already accepted trade.

        """
        # Define the input parameter data type
        sp.set_type(trade_id, sp.TNat)

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Check that the trade was not executed before
        self.check_trade_not_executed(trade_id)

        # Check that the sender is one of the trade users
        trade = self.data.trades[trade_id]
        self.check_is_user(trade.proposal)

        # Transfer the tokens to the user adddress
        sp.if sp.sender == trade.proposal.user1:
            # Check that the user accepted the trade before
            sp.verify(trade.user1_accepted,
                      message="The trade was not accepted before")

            # Change the status to not accepted
            trade.user1_accepted = False

            # Return all the editions to the user account
            sp.for token in trade.proposal.tokens1:
                self.fa2_transfer(
                    fa2=token.fa2,
                    from_=sp.self_address,
                    to_=sp.sender,
                    token_id=token.id,
                    token_amount=token.amount)
        sp.else:
            # Check that the user accepted the trade before
            sp.verify(trade.user2_accepted,
                      message="The trade was not accepted before")

            # Change the status to not accepted
            trade.user2_accepted = False

            # Return all the editions to the user account
            sp.for token in trade.proposal.tokens2:
                self.fa2_transfer(
                    fa2=token.fa2,
                    from_=sp.self_address,
                    to_=sp.sender,
                    token_id=token.id,
                    token_amount=token.amount)

    @sp.entry_point
    def execute_trade(self, trade_id):
        """Executes a trade.

        """
        # Define the input parameter data type
        sp.set_type(trade_id, sp.TNat)

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Check that the trade was not executed before
        self.check_trade_not_executed(trade_id)

        # Check that the sender is one of the trade users
        trade = self.data.trades[trade_id]
        self.check_is_user(trade.proposal)

        # Check that the two users accepted the trade
        sp.verify(trade.user1_accepted & trade.user2_accepted,
                  message="One of the users didn't accept the trade")

        # Set the trade as executed
        trade.executed = True

        # Transfer the first user tokens to the second user
        sp.for token in trade.proposal.tokens1:
            self.fa2_transfer(
                fa2=token.fa2,
                from_=sp.self_address,
                to_=trade.proposal.user2,
                token_id=token.id,
                token_amount=token.amount)

        # Transfer the second user tokens to the first user
        sp.for token in trade.proposal.tokens2:
            self.fa2_transfer(
                fa2=token.fa2,
                from_=sp.self_address,
                to_=trade.proposal.user1,
                token_id=token.id,
                token_amount=token.amount)

    def fa2_transfer(self, fa2, from_, to_, token_id, token_amount):
        """Transfers a number of editions of a FA2 token between two addresses.

        """
        # Get a handle to the FA2 token transfer entry point
        c = sp.contract(
            t=sp.TList(sp.TRecord(
                from_=sp.TAddress,
                txs=sp.TList(sp.TRecord(
                    to_=sp.TAddress,
                    token_id=sp.TNat,
                    amount=sp.TNat).layout(("to_", ("token_id", "amount")))))),
            address=fa2,
            entry_point="transfer").open_some()

        # Transfer the FA2 token editions to the new address
        sp.transfer(
            arg=sp.list([sp.record(
                from_=from_,
                txs=sp.list([sp.record(
                    to_=to_,
                    token_id=token_id,
                    amount=token_amount)]))]),
            amount=sp.mutez(0),
            destination=c)


# Add a compilation target
sp.add_compilation_target("simpleBarter", SimpleBarterContract())
