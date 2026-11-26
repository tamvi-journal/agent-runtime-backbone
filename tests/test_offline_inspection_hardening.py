import copy,pytest
from runtime.offline_executor import DockerOfflineExecutor,IsolationError

IMAGE="sha256:"+"1"*64

def good():
    return {"Image":IMAGE,"HostConfig":{"NetworkMode":"none","Privileged":False,"ReadonlyRootfs":True,
        "CapDrop":["ALL"],"UsernsMode":"","UTSMode":"","CgroupnsMode":"private","Runtime":"runc",
        "SecurityOpt":["no-new-privileges"],"MaskedPaths":["/proc/kcore","/proc/keys","/sys/firmware"],
        "ReadonlyPaths":["/proc/sys","/proc/irq","/proc/sysrq-trigger"],"MemorySwap":268435456,
        "Memory":268435456,"PidsLimit":64,"NanoCpus":1000000000},
        "Config":{"User":"65534:65534"},"NetworkSettings":{"Networks":{"none":{}}},
        "State":{"Status":"created","Running":False}}

def test_defense_in_depth_valid():
    DockerOfflineExecutor(image_id=IMAGE,docker="/usr/bin/docker")._validate_inspection(good())

@pytest.mark.parametrize("key,value",[
    ("UsernsMode","host"),("UTSMode","host"),("CgroupnsMode","host"),("Runtime","unknown"),
    ("SecurityOpt",["no-new-privileges","seccomp=unconfined"]),
    ("SecurityOpt",["no-new-privileges","apparmor=unconfined"]),
    ("MaskedPaths",[]),("ReadonlyPaths",[]),("MemorySwap",-1)])
def test_defense_in_depth_unsafe_values_denied(key,value):
    data=good();data["HostConfig"][key]=value
    with pytest.raises(IsolationError):DockerOfflineExecutor(image_id=IMAGE,docker="/usr/bin/docker")._validate_inspection(data)

def test_apparmor_unconfined_denied():
    data=good();data["AppArmorProfile"]="unconfined"
    with pytest.raises(IsolationError):DockerOfflineExecutor(image_id=IMAGE,docker="/usr/bin/docker")._validate_inspection(data)
