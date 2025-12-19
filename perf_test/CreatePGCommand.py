import sys

class CreatePGCommand:
    '''Returns PGCommand to execute based on the Test case and the PG Server provided'''

    @classmethod
    def pgcommand_to_execute(cls, server, testcase, pgserver_select1file, bin_directory):
        ''' Based on input server and test details, module will generate PGCommand to be executed
        This checks if the client VM is Ubuntu or Windows and create the command appropriately'''

        warmup_required = False
        print(server)

        pgcommand_bin = f"{bin_directory}/pgbench"

        # Connection parameters
        connection_params = " -h " + server["pgserver_hosturl"] + \
                           " -p " + server["pgserver_dbport"]
                           
        pgbench_initialize = f"{pgcommand_bin} -i" + connection_params

        pgbench_common = f"{pgcommand_bin} -P 10" + \
            " -M " + server["pgserver_testmode"] + connection_params

        # Get scale factor, connection and thread count for pgcommand based on server cores
        scale_factor, connections, threads = cls.calculate_scale_thread_connection(server, testcase)

        pgbenchcommand = pgbench_common + \
            " -c " + str(connections) + \
            " -j " + str(threads)

        if scale_factor:
            pgbenchcommand = pgbenchcommand + \
                " -s " + str(scale_factor)

            pgbench_initialize = pgbench_initialize + \
                " -s " + str(scale_factor)

        if "RO_" in testcase:
            pgbenchcommand = pgbenchcommand + \
                " -S "
            warmup_required = True

        if "RW_" in testcase:
            pgbench_initialize = pgbench_initialize + \
                " -F 90"
            warmup_required = True

        if "Select" in testcase:
            pgbenchcommand = pgbenchcommand + \
                " -f " + pgserver_select1file

        if warmup_required:
            pgbenchwarmupcommand = pgbenchcommand + \
                " -T " + str(server["pgserver_warmupduration"])
            pgbenchwarmupcommand = pgbenchwarmupcommand + " testdb"

        if "RW_" in testcase:
            pgbenchcommand = pgbenchcommand + \
                " -T " + str(server["pgserver_RW_testduration"])
        else:
            pgbenchcommand = pgbenchcommand + \
                " -T " + str(server["pgserver_testduration"])

        pgbenchcommand = pgbenchcommand + " testdb"
        pgbench_initialize = pgbench_initialize + " testdb"

        pgbench_dict = {}
        pgbench_dict["initialize"] = pgbench_initialize
        if warmup_required:
            pgbench_dict["warmupruns"] = pgbenchwarmupcommand
        pgbench_dict["testruns"] = pgbenchcommand

        return pgbench_dict

    @classmethod
    def calculate_scale_thread_connection(cls, server, testcase):
        ''' Returns scale factor, thread & connection counts for test based on server cores '''

        server_attribute = server
        v_cores = server_attribute["pgserver_vcore"]
        connections = int(server_attribute["pgserver_client_Multiplier"] * v_cores)
        threads = int(server_attribute["pgserver_thread_Multiplier"] * v_cores)

        if testcase == "Select1":
            scale_factor = None #For Select1, scale factor is not applicable
            connections = 1     #For Select1, connection count will be 1
            threads = 1         #For Select1, thread count will be 1
            return scale_factor, connections, threads

        if testcase == "Select1NPPS":
            scale_factor = None #For Select1NPPS, scale factor is not applicable
            return scale_factor, connections, threads

        if testcase == "RO_FullyCached":
            scale_factor = cls.calculate_scalefactor(server_attribute["pgserver_RO_fullCacheSF"], v_cores)
            return scale_factor, connections, threads

        if testcase == "RO_Borderline":
            scale_factor = cls.calculate_scalefactor(server_attribute["pgserver_RO_BorderLineSF"], v_cores)
            return scale_factor, connections, threads

        if testcase == "RW_FullyCached":
            scale_factor = cls.calculate_scalefactor(server_attribute["pgserver_RW_fullcacheSF"], v_cores)
            return scale_factor, connections, threads

        if testcase == "RO_FixedSF":
            scale_factor = server_attribute["pgserver_RO_FixedSF"]
            return scale_factor, connections, threads

        if testcase == "RW_FixedSF":
            scale_factor = server_attribute["pgserver_RW_FixedSF"]
            return scale_factor, connections, threads

        return None

    @classmethod
    def calculate_scalefactor(cls, sf_multiplier, v_cores):
        '''returns scale factor using SF multiplier and Vcore'''
        return int(sf_multiplier * v_cores / 2)
