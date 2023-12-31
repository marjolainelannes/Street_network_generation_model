##################################################################################
# Study: Street network generation
# Purpose: Define road network (nodes and edges)
# Author: Marjolaine Lannes
# Creation date: January 20, 2023
# Note: Merge consecutive roads, differentiate roads and PT links, add detailed geometry
##################################################################################
import pandas as pd
from shapely.geometry import LineString
from include.lines_geometry import segments_on_the_same_line, create_network_graph
from include.get_indexes import get_indexes
import numpy as np
import networkx as nx
import pickle as pkl

# Input/output files
path = "C:/Users/lannesadm/PycharmProjects/Road_network_topology/"
links_f = path + "temp/load_OSM/OSM_links.csv"
nodes_f = path + "temp/load_OSM/OSM_nodes.csv"
detailed_network_f = path + "data/OSM/ile_de_france_detailed_network.csv"
output_network_f = path + "temp/load_OSM/roads_links.csv"
output_nodes_roads = path + "temp/load_OSM/roads_nodes.csv"
output_preproc = path + "temp/load_OSM/roads_preprocessing.csv"

# Input df information
link_dtypes = {'id':str,'from':str,'to':str,'length':float,'freespeed':float,'capacity':float,'permlanes':float,'oneway':int,
               'modes':str, 'roundabout':bool, 'tunnel':bool}
node_dtypes =  {'id':str,'x':float,'y':float}
link_col = ['ID', 'NODE_A', 'NODE_B', 'XA', 'YA', 'XB', 'YB', 'LENGTH', 'ROUNDABOUT', 'TUNNEL', 'LINE']
node_col = ['ID', 'X', 'Y', 'LINKS']

# Load network information from OSM
Nodes = pd.read_csv(nodes_f, dtype=node_dtypes)
Nodes = Nodes.astype({'id': 'str'})
Links = pd.read_csv(links_f, dtype=link_dtypes)
Links = Links.astype({'id':'str'})
#n_links = Links.shape[0]
n_nodes = Nodes.shape[0]
n_links = Links.shape[0]
print("Number of nodes from OSM: ", n_nodes)
print("Number of edges from OSM: ", n_links)
detailed_network_df = pd.read_csv(detailed_network_f)
print("Data loaded...")

# Filter public transports
print("Filter public transports")
filter_railways = ['artificial,rail','artificial,subway','artificial,tram','artificial,stopFacilityLink,funicular',
                  'artificial,stopFacilityLink,tram','artificial,stopFacilityLink,rail','funicular,artificial',
                  'rail','subway,artificial,stopFacilityLink','subway,pt','train,pt,rail']
Railways = Links[Links['modes'].isin(filter_railways)].reset_index(drop=True)
Links_OSM = Links[~Links['modes'].isin(filter_railways)].reset_index(drop=True)
# Railways.to_csv(path + "temp/data/load_OSM/railways.csv", index=False)
print("Number of edges after filter: ", Links_OSM.shape[0])

# Merge double-way roads
## i.e. transform the directed multigraph into an undirected simple graph
print("Merge double-way roads")
roads_transform = {}
links_to_exclude = []
k=1
nodes = list(Nodes['id'])
G = create_network_graph(Links_OSM, Nodes)
# 1039072303
def comp(list1, list2):
    missing=[]
    for val in list1:
        if val not in list2:
            missing.append(val)
    return(missing)
for i, node_i in enumerate(nodes) :
    if int(n_nodes * k / 10) == i :
        print(k*10, "%")
        k += 1
    neighbourhood = [n for n in nx.all_neighbors(G,node_i)]
    nodes_list = [n for n in G.neighbors(node_i)]
    if len(neighbourhood) > len(nodes_list) :
        seen = set()
        duplicates = [x for x in neighbourhood if x in seen or seen.add(x)]
        for node_j in duplicates :
            edges_1 = G.get_edge_data(node_i, node_j)
            edges_2 = G.get_edge_data(node_j, node_i)
            if len(edges_1)==1 and len(edges_2)==1 :
                link_1 = str(edges_1[0]['id'])
                link_2 = str(edges_2[0]['id'])
                if not ((link_1 in links_to_exclude) or (link_2 in links_to_exclude)):
                    links_to_exclude.append(link_1)
                    roads_transform[link_1] = link_2
            else :
                identical_edges = []
                for i in range(0, len(edges_1)):
                    identical_edges.append(str(edges_1[i]['id']))
                for i in range(0, len(edges_2)):
                    identical_edges.append(str(edges_2[i]['id']))
                #print(identical_edges)
                if len(comp(identical_edges, links_to_exclude)) > 1 :
                    remaining_links = comp(identical_edges, links_to_exclude)
                    link_2 = remaining_links.pop(0)
                    for link_1 in remaining_links :
                        links_to_exclude.append(link_1)
                        roads_transform[link_1] = link_2
Links_OSM = Links_OSM[~Links_OSM['id'].isin(links_to_exclude)].reset_index(drop=True)
print("Double-way roads merged...")
Links_OSM.to_csv(path + "temp/data/load_OSM/double_way_roads_links.csv", index=False)
roads_transform_f1 = open(path + "temp/data/load_OSM/roads_transform_1.csv", 'wb')
pkl.dump(roads_transform, roads_transform_f1)
n_links = Links_OSM.shape[0]
print("Number of links after merging double-ways :", n_links)

# Merge consecutive roads again for modified streets
## i.e. drop nodes of order 2
print("Merge consecutive roads without intersection")
Nodes_OSM = Nodes.copy()
k=1
nodes_transform = {}
def get_keys_from_value(dict, value):
    return [item[0] for item in dict.items() if item[1] == value]
for i, node_i in enumerate(nodes) :
    if int(n_nodes * k / 10) == i :
        print(k*10, "%")
        k += 1
    nodes_A = list(Links_OSM['from'])
    nodes_B = list(Links_OSM['to'])
    links_indexes = get_indexes(nodes_A, node_i) + get_indexes(nodes_B, node_i)
    # if a node belongs to exactly two road links, drop the middle node and merge the two links
    if len(links_indexes) == 2:
        # get links and nodes ids
        link_1_index = links_indexes[0]
        link_2_index = links_indexes[1]
        link_1 = Links_OSM.loc[link_1_index, 'id']
        link_2 = Links_OSM.loc[link_2_index, 'id']
        node_A = Links_OSM.loc[link_1_index, 'from']
        node_B = Links_OSM.loc[link_1_index, 'to']
        node_C = Links_OSM.loc[link_2_index, 'from']
        node_D = Links_OSM.loc[link_2_index, 'to']
        # if the two links are exactly the same in opposite directions, just keep one
        if (node_A == node_D) and (node_B == node_C):
            # drop link_1
            roads_transform[link_1] = link_2
            Links_OSM = Links_OSM.drop([link_1_index], axis=0).reset_index(drop=True)
            # change the value of road_transform for roads previously transformed into link_1
            if link_1 in roads_transform.values():
                previously_merged_links = get_keys_from_value(roads_transform, link_1)
                for merged_link in previously_merged_links:
                    roads_transform[merged_link] = link_2
        elif (node_A == node_C) and (node_B == node_D):
            # drop link_1
            roads_transform[link_1] = link_2
            Links_OSM = Links_OSM.drop([link_1_index], axis=0).reset_index(drop=True)
            # change the value of road_transform for roads previously transformed into link_1
            if link_1 in roads_transform.values():
                previously_merged_links = get_keys_from_value(roads_transform, link_1)
                for merged_link in previously_merged_links:
                    roads_transform[merged_link] = link_2
        # if they are not, drop the middle node and merge the two links
        else :
            new_link_nodes = [node_A, node_B, node_C, node_D]
            # order nodes so that node_i is in the middle
            new_link_nodes = list(set(new_link_nodes))
            new_link_nodes.remove(node_i)
            link_nodes = new_link_nodes.copy()
            link_nodes.append(node_i)
            line = []
            for node_j in link_nodes:
                j = nodes.index(node_j)
                point = [Nodes.loc[j, 'x'], Nodes.loc[j, 'y']]
                line.append(point)
            # check if the angle between links is not too large
            are_on_the_same_line = segments_on_the_same_line(line[0], line[2], line[2], line[1])
            # if it is not, drop node_i and keep only one link (link_2)
            if are_on_the_same_line:
                # move node_i to the other node in link_2
                from_or_to = [node_C, node_D].index(node_i)
                other_node_id = [node_A, node_B]
                other_node_id.remove(node_i)
                targeted_node = other_node_id[0]
                if from_or_to == 0:  ## i.e. node_C = node_i = "from"
                    Links_OSM.loc[link_2_index, 'from'] = targeted_node
                    nodes_transform[node_i] = targeted_node
                    previously_merged_nodes = get_keys_from_value(nodes_transform, node_i)
                    for merged_node in previously_merged_nodes:
                        nodes_transform[merged_node] = targeted_node
                elif from_or_to == 1:  ## i.e. node_D = node_i = "to"
                    Links_OSM.loc[link_2_index, 'to'] = targeted_node
                    nodes_transform[node_i] = targeted_node
                    previously_merged_nodes = get_keys_from_value(nodes_transform, node_i)
                    for merged_node in previously_merged_nodes:
                        nodes_transform[merged_node] = targeted_node
                # drop link_1
                roads_transform[link_1] = link_2
                Links_OSM = Links_OSM.drop([link_1_index], axis=0).reset_index(drop=True)
                # change the value of road_transform for roads previously transformed into link_1
                if link_1 in roads_transform.values():
                    previously_merged_links = get_keys_from_value(roads_transform, link_1)
                    for merged_link in previously_merged_links:
                        roads_transform[merged_link] = link_2
print("Consecutive roads merged...")
nodes_to_exclude = list(nodes_transform.keys())
Nodes_OSM = Nodes_OSM[~Nodes_OSM['id'].isin(nodes_to_exclude)].reset_index(drop=True)
Links_OSM.to_csv(path + "temp/data/load_OSM/consecutive_roads_links.csv", index=False)
Nodes_OSM.to_csv(path + "temp/data/load_OSM/consecutive_roads_nodes.csv", index=False)
roads_transform_f2 = open(path + "temp/data/load_OSM/roads_transform_2.csv", 'wb')
pkl.dump(roads_transform, roads_transform_f2)
n_links = Links_OSM.shape[0]
print("Number of links after merging consecutive roads:", n_links)

# Save initial network transforms
Roads_preproc = pd.DataFrame(columns=['link_id','matching_link','pt'])
Roads_preproc['link_id'] = Links['id']
railways_ids = list(Railways['id'])
remaining_roads = list(Links_OSM['id'])
for i, link_id in enumerate(Links['id']):
    #save pt information
    if link_id in railways_ids :
        Roads_preproc.loc[i,'pt'] = True
        Roads_preproc.loc[i, 'matching_link'] = np.nan
    # save roads information
    else :
        Roads_preproc.loc[i, 'pt'] = False
        if link_id in remaining_roads :
            Roads_preproc.loc[i, 'matching_link'] = np.nan
        else :
            Roads_preproc.loc[i, 'matching_link'] = roads_transform[link_id]
Roads_preproc.to_csv(output_preproc, index=False)

# Save roads graph (edges and nodes) with coordinates for edges and links list for nodes
print("Now saving road graph")
Roads = pd.DataFrame(columns=link_col)
Roads_nodes = pd.DataFrame(columns=node_col)
for i in range (0,n_links) :
    # get link, node A and node B ids
    link_id = Links_OSM.loc[i, 'id']
    node_A_id = Links_OSM.loc[i, 'from']
    node_B_id = Links_OSM.loc[i, 'to']
    ## Update Roads_nodes
    # get nodes coordinates
    road_nodes = list(Roads_nodes['ID']) # get the list of existing road_nodes
    node_A = Nodes_OSM[Nodes_OSM.id == node_A_id].reset_index(drop=True)
    node_B = Nodes_OSM[Nodes_OSM.id == node_B_id].reset_index(drop=True)
    xa = float(node_A.loc[0, 'x'])
    ya = float(node_A.loc[0, 'y'])
    xb = float(node_B.loc[0, 'x'])
    yb = float(node_B.loc[0, 'y'])
    # save node A coordinates and new link id
    if node_A_id in road_nodes : # if the node already exists
        node_A_index = Roads_nodes[Roads_nodes.ID == node_A_id].index[0]
        links_list_node_A = Roads_nodes.loc[node_A_index, 'LINKS']
        links_list_node_A.append(link_id)
        Roads_nodes.loc[node_A_index, 'LINKS'] = links_list_node_A
    else :
        node_A_row = pd.DataFrame(columns=node_col)
        node_A_row.loc[0,'ID'] = node_A_id
        node_A_row.loc[0,'X'] = xa
        node_A_row.loc[0,'Y'] = ya
        node_A_row.loc[0,'LINKS'] = [link_id]
        Roads_nodes = pd.concat([Roads_nodes, node_A_row], ignore_index=True)
    # save node B coordinates and new link id
    if node_B_id in road_nodes : # if the node already exists
        node_B_index = Roads_nodes[Roads_nodes.ID == node_B_id].index[0]
        links_list_node_B = Roads_nodes.loc[node_B_index, 'LINKS']
        links_list_node_B.append(link_id)
        Roads_nodes.loc[node_B_index, 'LINKS'] = links_list_node_B
    else :
        node_B_row = pd.DataFrame(columns=node_col)
        node_B_row.loc[0,'ID'] = node_B_id
        node_B_row.loc[0,'X'] = xb
        node_B_row.loc[0,'Y'] = yb
        node_B_row.loc[0,'LINKS'] = [link_id]
        Roads_nodes = pd.concat([Roads_nodes, node_B_row], ignore_index=True)
    ## Update Roads (links)
    # save link coordinates and geometry
    link_row = pd.DataFrame(columns=link_col)
    link_row.loc[0, 'ID'] = link_id
    link_row.loc[0, 'NODE_A'] = node_A_id
    link_row.loc[0, 'NODE_B'] = node_B_id
    link_row.loc[0, 'XA'] = xa
    link_row.loc[0, 'YA'] = ya
    link_row.loc[0, 'XB'] = xb
    link_row.loc[0, 'YB'] = yb
    link_row.loc[0, 'LENGTH'] = LineString([(xa, ya), (xb, yb)]).length
    link_row.loc[0, 'TUNNEL'] = Links_OSM.loc[i, 'tunnel']
    link_row.loc[0, 'ROUNDABOUT'] = Links_OSM.loc[i, 'roundabout']
    link_row.loc[0, 'LINE'] = LineString([(xa, ya), (xb, yb)])
    Roads = pd.concat([Roads, link_row], ignore_index=True)
    if i % 1000 == 0 :
        print(i)
print("OSM network saved in edges and nodes dataframes...")
Roads.to_csv(path + "temp/data/load_OSM/geo_roads_links.csv", index = False)
Roads_nodes.to_csv(output_nodes_roads, index = False)

# Get detailed geometry for each road
print("Get detailed geometry for each road")
ids_with_detailed_geom = list(detailed_network_df['LinkId'])
merged_roads = list(roads_transform.values())
for i,road_id in enumerate(Roads['ID']):
    if (not (road_id in merged_roads)) and (road_id in ids_with_detailed_geom) :
        road_i = detailed_network_df[detailed_network_df.LinkId == road_id].reset_index(drop=True)
        Roads.loc[i,'GEOMETRY'] = road_i.loc[0, 'Geometry']
    else :
        Roads.loc[i, 'GEOMETRY'] = Roads.loc[i, 'LINE']
print("Detailed geometry added...")

# Save data
Roads.to_csv(output_network_f, index = False)
