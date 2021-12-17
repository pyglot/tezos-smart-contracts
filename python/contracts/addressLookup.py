import smartpy as sp

class AddressLookup(sp.Contract):
    """Contract to allow a global lookup register between Address and ID (nat).
    The use-case is to save on gas in contracts where addresses are frequently stored.

    Two cryptic error messages:
        UNKNOWN = The address or id is not registered.
        REREG   = The address or id has previously been registered and can't reregister.
        ID_NEQ_SENDER = The address of id is not the sender's address.
        ID_NEQ_ADDR = The address of id is not the address in addr.

    Notes: It may be useful for this contract to get a Michelson optimization to save on gas.        

    """
    def __init__(self, addr2id, id2addr, counter):
        """Initializes the contract. 
        
        Initialization is a bit fragile, could be improved, but used only at origination ...

        """

        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            addr2id=sp.TBigMap(sp.TAddress, sp.TNat),
            id2addr=sp.TBigMap(sp.TNat, sp.TAddress),
            counter=sp.TNat))

        self.init(addr2id=addr2id,id2addr=id2addr,counter=counter)

    @sp.onchain_view(name="has_addr")
    def view_has_addr(self,param):
        sp.set_type(param,sp.TAddress)
        sp.result(self.data.addr2id.contains(param))

    @sp.onchain_view(name="has_sender")
    def view_has_sender(self):
        sp.result(self.data.addr2id.contains(sp.sender))

    @sp.onchain_view(name="chk_idEqSender")
    def view_verify_id_equale_sender(self, id):
        sp.set_type(id,sp.TNat)
        sp.verify(self.data.id2addr[id]==sp.sender,message="ID_NEQ_SENDER")

    @sp.onchain_view(name="chk_idEqAddr")
    def view_verify_id_equ_addr(self,params):
        sp.set_type(params.id,sp.TNat)
        sp.set_type(params.addr,sp.TAddress)
        sp.verify(self.data.id2addr[params.id]==params.addr,message="ID_NEQ_ADDR")
    
    @sp.onchain_view(name="get_counter")
    def view_get_counter(self):
        sp.result(self.data.counter)

    @sp.onchain_view(name="addr2id")
    def view_addr2id(self,param):
        sp.set_type(param,sp.TAddress)
        sp.verify(self.data.addr2id.contains(param),message="UNKNOWN")
        sp.result(self.data.addr2id.get(param, default_value=None))

    @sp.onchain_view(name="id2addr")
    def view_id2addr(self,param):
        sp.set_type(param,sp.TNat)
        sp.verify(self.data.id2addr.contains(param),message="UNKNOWN")
        sp.result(self.data.id2addr.get(param, default_value=None))

    @sp.entry_point
    def register(self):
        """Register the sender. Fails if already known to avoid double spend."""
        sp.verify(~self.data.addr2id.contains(sp.sender),message="REREG")
        self.data.addr2id[sp.sender] = self.data.counter
        self.data.id2addr[self.data.counter] = sp.sender
        self.data.counter += 1

    @sp.entry_point
    def register_addr(self, param):
        """Register the address. Fails if already known to avoid double spend."""
        sp.set_type(param, sp.TAddress)
        sp.verify(~self.data.addr2id.contains(param),message="REREG")
        self.data.addr2id[param] = self.data.counter
        self.data.id2addr[self.data.counter] = param
        self.data.counter += 1

# Origination params
nulladdr = sp.address("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU")
burnaddr = sp.address("tz1burnburnburnburnburnburnburjAYjjX")
addr2id = sp.big_map({nulladdr:0,burnaddr:1}, sp.TAddress, sp.TNat)
id2addr = sp.big_map({0:nulladdr,1:burnaddr}, sp.TNat, sp.TAddress)

class LookupAddress(sp.Contract):
    "To test AddressLookup"
    aaa_rtype = sp.TRecord(a=sp.TAddress, b=sp.TAddress, c=sp.TAddress)
    nnn_rtype = sp.TRecord(a=sp.TNat,b=sp.TNat,c=sp.TNat)
    aaa_type = sp.TBigMap(sp.TNat,aaa_rtype)
    nnn_type = sp.TBigMap(sp.TNat,nnn_rtype)

    def __init__(self,id_aaa,id_nnn,id_reg):
        "To test the views"

        self.init_type(
            sp.TRecord(
              id_aaa=LookupAddress.aaa_type,
              id_nnn=LookupAddress.nnn_type,
              id_reg=sp.TAddress
              )
            )

        self.init( id_aaa=id_aaa,
                   id_nnn=id_nnn,
                   id_reg=id_reg
                 )

    @sp.entry_point
    def store_aaa(self,i,addr):
        """Test registering three addresses. To find storage cost."""
        sp.set_type(i,sp.TNat)
        sp.set_type(addr,sp.TAddress)
        self.data.id_aaa[i] = sp.record(a=addr,b=addr,c=addr)

    @sp.entry_point
    def lui_store_aaa(self,i,id):
        """Test registering three addresses. To find storage cost."""
        sp.set_type(i,sp.TNat)
        sp.set_type(id,sp.TNat)
        addr = sp.view("id2addr", self.data.id_reg, id, t = sp.TAddress).open_some()
        self.data.id_aaa[i] = sp.record(a=addr,b=addr,c=addr)

    @sp.entry_point
    def store_nnn(self,i,id):
        """Test registering three addresses. To find storage cost."""
        sp.set_type(i,sp.TNat)
        sp.set_type(id,sp.TNat)
        self.data.id_nnn[i] = sp.record(a=id,b=id,c=id)

    @sp.entry_point
    def lua_store_nnn(self,i,addr):
        """Test registering three addresses. To find storage cost."""
        sp.set_type(i,sp.TNat)
        sp.set_type(addr,sp.TAddress)
        id = sp.view("addr2id", self.data.id_reg, addr, t = sp.TNat).open_some()
        self.data.id_nnn[i] = sp.record(a=id,b=id,c=id)


# Test related
acc1 = sp.test_account("account1")
acc2 = sp.test_account("account2")
acc3 = sp.test_account("account3")

a=acc1.address
i=0

id_aaa=sp.big_map()
id_nnn=sp.big_map()

@sp.add_test(name = "AddressLookup")
def test():
    scenario = sp.test_scenario()
    
    c1 = AddressLookup(addr2id,id2addr,2)
    scenario += c1
    c2 = LookupAddress(id_aaa,id_nnn,c1.address)
    scenario += c2

    scenario.h1("Test basics")

    scenario += c1.register().run(valid=True,  sender=acc1)    
    scenario += c1.register().run(valid=True,  sender=acc2)
    scenario += c1.register().run(valid=False, sender=acc1)
    scenario += c1.register().run(valid=False, sender=acc2)
    scenario.verify(c1.view_addr2id(acc1.address)==2)
    scenario.verify(c1.view_id2addr(2)==acc1.address)
    scenario.verify(c1.view_addr2id(acc2.address)==3)
    scenario.verify(c1.view_id2addr(3)==acc2.address)
    scenario.verify(c1.view_get_counter()==4)
    scenario.verify(c1.view_has_addr(acc2.address)==True)
    scenario.verify(c1.view_has_addr(acc1.address)==True)
    scenario.verify(c1.view_has_addr(nulladdr)==True)
    scenario.verify(c1.view_has_addr(acc3.address)==False)

    scenario.h1("Test views")

    scenario += c2.store_aaa(sp.record(i=0,addr=acc1.address)).run(valid=True, sender=acc1)
    scenario += c2.store_nnn(sp.record(i=1,id=1)).run(valid=True, sender=acc1)
    scenario += c2.store_nnn(sp.record(i=2,id=1000000000000000000000000000000000000)).run(valid=True, sender=acc1)
    scenario += c2.lui_store_aaa(sp.record(i=3,id=0)).run(valid=True, sender=acc1)
    scenario += c2.lua_store_nnn(sp.record(i=4,addr=nulladdr)).run(valid=True, sender=acc1)
    

sp.add_compilation_target("address_lookup", AddressLookup(addr2id, id2addr , 2))
sp.add_compilation_target("lookup_address_test", LookupAddress(id_aaa, id_nnn, sp.address("address-of-address_lookup")))
