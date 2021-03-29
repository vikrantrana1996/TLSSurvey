import concurrent.futures
import redis
from sslyze import (
    ServerNetworkLocationViaDirectConnection,
    ServerConnectivityTester,
    Scanner,
    ServerScanRequest,
    ScanCommand,
)
from sslyze.errors import ConnectionToServerFailed
r=redis.Redis(host='127.0.0.1',port='6379')

def runsslyze(seq):
    hostname=r.hget(seq,"hostname")
    status=r.hget(seq,"STATUS")
    if str(status)=='0' or not status:
        scan_runner(seq,hostname)
    return


def scan_runner(seq,host):
    hostname=host.decode("utf-8")
    servers_to_scan = []
    server_location = None
    try:
        if r.hget(seq,"ipaddr"):
            server_location = ServerNetworkLocationViaDirectConnection(hostname, 443, r.hget(seq,"ipaddr").decode("utf-8"))
        else:
            server_location = ServerNetworkLocationViaDirectConnection.with_ip_address_lookup(hostname, 443)
            r.hset(seq,"ipaddr",server_location.ip_address)
        #Initialize with hostname, port int and ip address str 
        #print(server_location)
    except Exception as e:
        print(e)
        r.hset(seq,"STATUS",2)
    try:
        server_info = ServerConnectivityTester().perform(server_location)
        servers_to_scan.append(server_info)
    except ConnectionToServerFailed as e:
        r.hset(seq,"STATUS",3)
        return

    scanner = Scanner()

    # Then queue some scan commands for each server
    for server_info in servers_to_scan:
        server_scan_req = ServerScanRequest(
            server_info=server_info, scan_commands={ScanCommand.TLS_1_3_CIPHER_SUITES},
        )
        scanner.queue_scan(server_scan_req)

    # Then retrieve the result of the scan commands for each server
    for server_scan_result in scanner.get_results():
        try:
            tls1_3_result = server_scan_result.scan_commands_results[ScanCommand.TLS_1_3_CIPHER_SUITES]
            if tls1_3_result.accepted_cipher_suites:
                r.hset(seq,"TLS1_3","True")
            r.hset(seq,"STATUS",1)
            
        except KeyError:
            r.hset(seq,"STATUS",4)


        # Scan commands that were run with errors
        for scan_command, error in server_scan_result.scan_commands_errors.items():
            r.hset(seq,"STATUS",5)


if __name__ == "__main__":
    i=1
    workers=1000
    while i<=100000:
        sequences=[]
        for j in range(i,i+workers):
            sequences.append(j)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for sequence in sequences:
                executor.submit(runsslyze,seq=sequence)
            executor.shutdown(wait=True)
        print("Current Iteration at ",i)
        i=i+workers

