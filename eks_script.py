import subprocess
import parameters
import sys
import time
import random

version="1.0.0"
ns=""
divider="--------------------------------------"
se_user=False
create_cluster=False
create_couchmart=True

def check_ns():
	print("Running eks deployment script")
	if sys.version_info[0] < 3:
		ns = raw_input("Enter a namespace : ")
	else:
		ns = input("Enter a namespace : ")
	print("Checking ns[{}]".format(ns))

	for x in range(parameters.NS_ATTEMPTS):
		print("Checking attempt #{}".format(x))
		p=subprocess.Popen('kubectl get ns', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		for line in p.stdout.readlines():
			spaces=line.split()
			if spaces[0].decode('ascii') == ns:
				return ""
		retval = p.wait()
		time.sleep(random.randint(1,parameters.NS_WAIT_VARIANCE))
		

	return ns

def execute_command(command):
	print(divider)
	print("Executing command : {}".format(command))
	p=subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	for line in p.stdout.readlines():
		print(line)
	retval = p.wait()

	if retval != 0:
		print ("Error encountered running command: {}".format(command))
		sys.exit(retval)

def create_namespace_yaml():
	f = open("./resources/namespace.yaml","w")
	f.write("kind: Namespace\n")
	f.write("apiVersion: v1\n")
	f.write("metadata:\n")
	f.write("  name: {0}\n".format(ns))
	f.write("  labels:\n")
	f.write("    name: {0}\n".format(ns))
	f.close()

def check_status(ns):
	print(divider)

	retVal=False
	maxTry=parameters.CM_RETRY_ATTEMPTS
	myTry=1

	while retVal == False and myTry <= maxTry:
		print ("Checking couchmart pod status : attempt {}".format(myTry))
		myTry = myTry + 1
		p=subprocess.Popen("kubectl get pods --namespace {}".format(ns), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		for line in p.stdout.readlines():
			spaces=line.split()
			if "couchmart" in spaces[0].decode('ascii'):
				if spaces[1].decode('ascii') == "1/1":
					print(spaces[0].decode('ascii') + "  " + spaces[1].decode('ascii'))
					retVal=True
				else:
					print(spaces[0].decode('ascii') + "  " + spaces[1].decode('ascii'))
		
		time.sleep(parameters.CM_WAIT_TIME_SEC)

	return retVal

def update_settings_py(ns):
	print(divider)
	print("updating setting.py")

	name = "unknown"
	str_lit = "\\\"cb-example-{0}.cb-example.{1}.svc\\\""

	p=subprocess.Popen("kubectl get pods --namespace {}".format(ns), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	for line in p.stdout.readlines():
		spaces=line.split()
		if "couchmart" in spaces[0].decode('ascii'):
			name=spaces[0].decode('ascii')
			break

	execute_command("kubectl exec -it {0} --namespace {1} -- sed -e 3d -i.bkup /couchmart/settings.py".format(name,ns))
	execute_command("kubectl exec -it {0} --namespace {1} -- sed -e \"2a AWS_NODES = [{2},{3},{4}]\" -i.bkup /couchmart/settings.py".format(
		name,ns,str_lit.format("0000",ns),str_lit.format("0001",ns),str_lit.format("0002",ns)))

def usage():
	print("python eks_script.py [--create-crd] [--create-cb-cluster] [--no-couchmart] [-h|--help]")
	print("version: {}".format(version))
	print("")
	print("	--create-crd  		== Create the cluster level resources such as CRD and ClusterRole")
	print("	--create-cb-cluster	== Create the couchbase cluster automatically")
	print("	--no-couchmart		== Disable creation of the Couchmart demo application pod")

if __name__ == "__main__":

	#Check if SE user is flagged
	for x in sys.argv:
		y = x.upper()
		if y == "SEUSER" or y == "--CREATE-CRD":
			se_user = True
		elif y == "--CREATE-CB-CLUSTER":
			create_cluster = True
		elif y == "--NO-COUCHMART":
			create_couchmart = False
		elif y == "EKS_SCRIPT.PY":
			continue
		elif y == "-H" or y == "--HELP":
			usage()
			sys.exit(0)
		else:
			print ("Unknown flag {}".format(x))
			usage()
			sys.exit(1)
		

	ns = check_ns()
	if len(ns) <= 0:
		print("Namespace was already detected or cant be blank")
		sys.exit()

	create_namespace_yaml()
	execute_command("kubectl create -f ./resources/namespace.yaml")
	execute_command("kubectl create -f ./resources/serviceaccount-couchbase.yaml --namespace {}".format(ns))
	if se_user:
		execute_command("kubectl create -f ./resources/cluster-role.yaml --namespace {}".format(ns))

	execute_command("kubectl create -f ./resources/rolebinding.yaml --namespace {}".format(ns))

	# Cluster level resource only needs to be run once
	if se_user:
		execute_command("kubectl create -f ./resources/crd.yaml --namespace {}".format(ns))

	execute_command("kubectl create -f ./resources/operator.yaml --namespace {}".format(ns))
	execute_command("kubectl create -f ./resources/secret.yaml --namespace {}".format(ns))

	#Launch Couchmart Environment
	try:
		tag=parameters.COUCHMART_TAG
	except AttributeError:
		tag="python2"

	if create_couchmart:
		print(divider)
		print("Creating couchmart from cbck/couchmart:{}".format(tag))
		execute_command("kubectl run couchmart --image=cbck/couchmart:{0} --namespace {1}".format(tag,ns))	

		print(divider)
		print("Checking completion status of couchmart pod")
		if check_status(ns) == True:
			update_settings_py(ns)
		else:
			print("No running Couchmart Pod detected...")

	if create_cluster:
		execute_command("kubectl create -f ./resources/couchbase-cluster.yaml --namespace {}".format(ns))
