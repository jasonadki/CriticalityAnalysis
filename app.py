from flask import Flask, request, jsonify
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import seaborn as sns
from collections import deque
from datetime import datetime
import os
import json
import pandas as pd

def generate_filename(prefix, extension):
    """Generate a filename with a timestamp and a given prefix and extension.
    
    :param prefix: <str> The prefix to use for the filename.
    :param extension: <str> The extension to use for the filename.
    
    :return: <str> The generated filename.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    directory = 'saved_files'
    if not os.path.exists(directory): # Create the directory if it doesn't exist
        os.makedirs(directory)
    filename = f"{prefix}_{timestamp}.{extension}"
    return os.path.join(directory, filename)



app = Flask(__name__)

@app.route('/bottom_up_process', methods=['POST'])
def bottom_up_process():
    """
    Calculate the percentage use of data for each mission using a bottom-up process where the data usage of a mission is the average of its children.
    """
    data = request.json
    
    print(f'DATA: {data}')

    # Parse missions and operational data
    missions = {m['UUID']: {'label': m['Name']} for m in data['Mission']}
    operational_data = {d['UUID']: {'label': d['Name'], 'shape': 'box'} for d in data['OperationalData']}

    # Combine mission and data nodes
    full_nodes = {**missions, **operational_data}

    # Parse mission hierarchy and mission-operational data relationships
    mission_hierarchy = [(rel['ChildMission'], rel['ParentMission']) for rel in data['MissionHierarchy']]
    mission_data_relations = [(rel['OperationalData'], rel['Mission']) for rel in data['Mission_OperationalData']]

    # Create matrix
    matrix = np.zeros((len(missions), len(operational_data)))

    # Create and populate graph
    G = nx.DiGraph()
    G.add_nodes_from(full_nodes.keys())
    G.add_edges_from(mission_hierarchy + mission_data_relations)

    # Create mission-only graph
    M = nx.DiGraph()
    M.add_nodes_from(missions.keys())
    M.add_edges_from(mission_hierarchy)

    # Function to find leaf mission nodes
    def find_leaf_mission_nodes(graph):
        return [n for n in graph.nodes() if graph.in_degree(n) == 0]

    # Determine traversal path
    try:
        traversal_path = list(nx.topological_sort(M))
        print("Traversal Path: ", traversal_path)
    except nx.NetworkXUnfeasible:
        print("Graph has a cycle, so a topological sort is not possible.")

    # Find leaf mission nodes
    leaf_mission_nodes = find_leaf_mission_nodes(M)

    # UUID to Index mappings
    mission_to_index = {uuid: i for i, uuid in enumerate(missions)}
    data_to_index = {uuid: i for i, uuid in enumerate(operational_data)}

    # Calculate the percentage use of data for each mission
    for m_uuid in traversal_path:
        # Get the index of the mission
        m_index = mission_to_index[m_uuid]

        if m_uuid in leaf_mission_nodes:
            # If the mission is a leaf node, assign 100% data usage to connected data nodes
            connected_data_nodes = [n for n in G.predecessors(m_uuid) if n in operational_data]
            for d_uuid in connected_data_nodes:
                matrix[m_index][data_to_index[d_uuid]] = 100
        else:
            # If the mission has children, calculate the average data usage from its children
            children = [n for n in M.predecessors(m_uuid) if n in missions]
            
            # Get the data usage of the children
            children_rows = [matrix[mission_to_index[c]] for c in children]

            if children_rows:
                # Calculate the average manually for better debugging
                calculated_mean = np.sum(children_rows, axis=0) / len(children_rows)
                matrix[m_index] = calculated_mean
            else:
                # If the mission has no children, assign 0% data usage to all operational data
                matrix[m_index] = np.zeros(len(operational_data))
       
        
    # Pretty print matrix
    mission_labels = [missions[uuid]['label'] for uuid in missions]
    data_labels = [operational_data[uuid]['label'] for uuid in operational_data]

    # Create a heatmap for the matrix
    plt.figure(figsize=(10, 6))
    sns.heatmap(matrix, annot=True, fmt=".2f", cmap="YlGnBu", xticklabels=data_labels, yticklabels=mission_labels)
    plt.title("Percentage Use of Data for Each Mission")
    plt.xlabel("Data")
    plt.ylabel("Missions")
    heatmap_filename = generate_filename("heatmap_bottom_up", "png")
    plt.savefig(heatmap_filename)
    plt.close()  # Close the plot to free memory
    
    # Save the values in a CSV file including the labels
    csv_filename = generate_filename("matrix_bottom_up", "csv")
    with open(csv_filename, 'w') as f:
        f.write(',' + ','.join(data_labels) + '\n')
        for i, row in enumerate(matrix):
            f.write(mission_labels[i] + ',' + ','.join(map(str, row)) + '\n')
            
    # Return the results file names
    process_results = {
        "message": "Bottom-up process completed",
        "heatmap_filename": heatmap_filename,
        "csv_filename": csv_filename
    }

    return jsonify(process_results)


# Calculating Depth and Breadth
def calculate_depth(graph, node_id, visited=set()):
    if node_id in visited:
        return 0
    visited.add(node_id)
    depths = [calculate_depth(graph, predecessor, visited) for predecessor in graph.predecessors(node_id)]
    return 1 + max(depths) if depths else 0

# Calculate the breadth of a node (number of children)
def calculate_breadth(graph, node_id):
    return len(list(graph.successors(node_id)))
    

@app.route('/bfs_dfs_analysis', methods=['POST'])
def bfs_dfs_analysis():
    """
    Perform a Depth and Breadth analysis of the mission hierarchy and mission-operational data relationships.
    (I think this actually is not interesting since Operational Data is unidirectional to Missions)
    
    """
    data = request.json

    # Parse missions and operational data
    missions = {m['UUID']: {'label': m['Name']} for m in data['Mission']}
    operational_data = {d['UUID']: {'label': d['Name'], 'shape': 'box'} for d in data['OperationalData']}

    # Combine mission and data nodes
    full_nodes = {**missions, **operational_data}

    # Parse mission hierarchy and mission-operational data relationships
    mission_hierarchy = [(rel['ChildMission'], rel['ParentMission']) for rel in data['MissionHierarchy']]
    mission_data_relations = [(rel['OperationalData'], rel['Mission']) for rel in data['Mission_OperationalData']]
    
    # Create and populate graph
    G = nx.DiGraph()
    G.add_nodes_from(full_nodes.keys())
    G.add_edges_from(mission_hierarchy + mission_data_relations)

    
    # Calculate the depth and breadth of each node in the graph
    criticality_scores = {}
    for node_id in operational_data:
        depth = calculate_depth(G, node_id)
        breadth = calculate_breadth(G, node_id)
        # Simple criticality score: higher values for more "leaf" nodes, adjusted by depth
        criticality_scores[node_id] = breadth + 1 / (depth + 1)  # Avoid division by zero

    # Normalize the criticality scores to a 1-4 range
    max_score = max(criticality_scores.values(), default=1)
    min_score = min(criticality_scores.values(), default=0)
    normalized_scores = {node_id: 1 + 3 * (score - min_score) / (max_score - min_score) if max_score > min_score else 1 for node_id, score in criticality_scores.items()}

    # Prepare both sets of scores with labels for saving
    scores_info = {
        'normalized_scores': {operational_data[node_id]['label']: score for node_id, score in normalized_scores.items()},
        'non_normalized_scores': {operational_data[node_id]['label']: score for node_id, score in criticality_scores.items()}
    }

    # Save the scores in a JSON file including the labels
    json_filename = generate_filename("scores_bfs_dfs", "json")
    with open(json_filename, 'w') as f:
        json.dump(scores_info, f, indent=4)


    # Return the results file names
    response = {
        "message": "Depth and Breadth analysis completed",
        "criticality_scores": scores_info['normalized_scores'],
        "results_file": json_filename
    }

    return jsonify(response)


    
    
    
    
# Function to find the shortest path
def find_shortest_path(graph, start, end):
    visited = set()
    queue = deque([[start]])
    
    # BFS
    while queue:
        # Get the path
        path = queue.popleft()
        # Get the last node in the path
        node = path[-1]
        
        # Check if the node is the end node
        if node == end:
            return path
        
        # Check if the node has been visited
        if node not in visited:
            # Add the node to the visited set
            visited.add(node)
            # Get the neighbors of the node
            neighbors = graph.successors(node)
            
            # Add the neighbors to the queue
            for neighbor in neighbors:
                new_path = list(path)
                new_path.append(neighbor)
                queue.append(new_path)
    
    return []

# Function to adjust score for path length
def adjust_score_for_path_length(score, path_length):
    return score / path_length if path_length > 0 else 0

# Function to get all dependencies of a node in a recursive manner
def get_all_dependencies(graph, node_id):
    direct_dependencies = list(graph.predecessors(node_id))
    all_dependencies = set(direct_dependencies)
    
    for dep_node_id in direct_dependencies:
        all_dependencies.update(get_all_dependencies(graph, dep_node_id))
    
    return list(all_dependencies)


@app.route('/pagerank_analysis', methods=['POST'])
def pagerank_analysis():
    """
    Perform a PageRank analysis of the mission hierarchy and mission-operational data relationships.
    """
    data = request.json  # Retrieves JSON data sent to the endpoint

    G = nx.DiGraph()  # Initializes a directed graph

    # Creates nodes for missions and operational data with properties such as name, type, and color
    missions = [(mission['UUID'], {'label': mission['Name'], 'type': 'Mission', 'color': 'red'}) for mission in data['Mission']]
    operational_data = [(op_data['UUID'], {'label': op_data['Name'], 'type': 'OperationalData', 'color': 'grey'}) for op_data in data['OperationalData']]
    G.add_nodes_from(missions + operational_data)  # Adds these nodes to the graph

    # Create edges for mission hierarchy and mission-operational data relationships
    mission_hierarchy_edges = [(hierarchy['ParentMission'], hierarchy['ChildMission']) for hierarchy in data['MissionHierarchy']]
    mission_operational_data_edges = [(association['Mission'], association['OperationalData']) for association in data['Mission_OperationalData']]
    G.add_edges_from(mission_hierarchy_edges + mission_operational_data_edges)  # Adds these edges to the graph

    page_rank = nx.pagerank(G, alpha=0.85)  # Computes PageRank for each node in the graph

    # Assign PageRank scores to node attributes in the graph
    for n in G.nodes:
        G.nodes[n]['pageRank'] = page_rank[n]

    # Function to find the shortest path between two nodes
    def find_shortest_path(graph, start, end):
        visited = set()
        queue = deque([[start]])
        while queue:
            path = queue.popleft()
            node = path[-1]
            if node == end:
                return path
            if node not in visited:
                visited.add(node)
                for neighbor in graph.successors(node):
                    new_path = list(path) + [neighbor]
                    queue.append(new_path)
        return []

    # Function to adjust the PageRank score based on the path length to reflect influence over distance.
    # A shorter path from a mission to an operational data node implies stronger influence, 
    # hence the division by path length to normalize the score inversely with distance.
    def adjust_score_for_path_length(score, path_length):
        # Return the adjusted score, which is the original score divided by the path length.
        # If path length is zero (i.e., no path exists), return 0 to avoid division by zero.
        return score / path_length if path_length > 0 else 0

    # Function to recursively find all dependencies of a node in a directed graph.
    # This function accumulates all nodes that can be reached directly or indirectly 
    # from the given node and can be used to assess the extent of influence or dependency.
    def get_all_dependencies(graph, node_id):
        # Retrieve direct successors (dependencies) of the node.
        direct_dependencies = list(graph.successors(node_id))
        # Initialize a set to keep track of all dependencies, including indirect ones.
        all_dependencies = set(direct_dependencies)
        # Recursively get dependencies of each direct dependency.
        for dep_node_id in direct_dependencies:
            all_dependencies.update(get_all_dependencies(graph, dep_node_id))
        # Convert the set of all dependencies to a list before returning.
        return list(all_dependencies)

    # Calculate importance scores for each mission based on dependencies on operational data.
    # This block determines how critical each piece of operational data is for each mission.
    missions_importance_scores = {}
    for mission_uuid, mission_info in missions:
        # Get all dependencies for the mission, both direct and indirect.
        dependencies = get_all_dependencies(G, mission_uuid)
        # Use a set to ensure each dependency is only considered once.
        unique_dependencies = set(dependencies)
        adjusted_scores = {}
        total_adjusted_score = 0
        # Iterate over each unique dependency.
        for node_id in unique_dependencies:
            # Only consider operational data nodes for importance scoring.
            if G.nodes[node_id].get('type') == 'OperationalData':
                # Calculate the path length from the mission to the operational data node.
                path_length = len(find_shortest_path(G, mission_uuid, node_id))
                # Adjust the PageRank score by the path length.
                adjusted_score = adjust_score_for_path_length(G.nodes[node_id]['pageRank'], path_length)
                # Accumulate the adjusted score for normalization later.
                adjusted_scores[node_id] = adjusted_score
                total_adjusted_score += adjusted_score
        # Normalize scores so they sum to 1 across all dependencies for each mission.
        for node_id in adjusted_scores:
            adjusted_scores[node_id] /= total_adjusted_score if total_adjusted_score > 0 else 1
        # Store the normalized scores for each mission.
        missions_importance_scores[mission_uuid] = adjusted_scores


    # Generate filenames and save scores to JSON file
    json_filename = generate_filename("pagerank_analysis_missions", "json")
    mission_data_scores = {mission_uuid: {node_id: score for node_id, score in mission_scores.items()} 
                           for mission_uuid, mission_scores in missions_importance_scores.items()}
    with open(json_filename, 'w') as f:
        json.dump(mission_data_scores, f, indent=4)

    # Add operational data not linked as dependencies with a score of 0
    for mission_idx, mission_dtl in enumerate(missions):
        mission_uuid = mission_dtl[0]
        for data_idx, data_dtl in enumerate(operational_data):
            data_uuid = data_dtl[0]
            if data_uuid not in mission_data_scores[mission_uuid].keys():
                mission_data_scores[mission_uuid][data_uuid] = 0

    # Create a matrix for the scores and save to CSV and PNG
    matrix = np.zeros((len(missions), len(operational_data)))
    for mission_idx, mission_dtl in enumerate(missions):
        mission_uuid = mission_dtl[0]
        for data_idx, data_dtl in enumerate(operational_data):
            data_uuid = data_dtl[0]
            matrix[mission_idx, data_idx] = mission_data_scores[mission_uuid][data_uuid]
    plt.figure(figsize=(20, 10))
    sns.heatmap(matrix, annot=True, fmt=".2f", cmap="YlGnBu", xticklabels=[data_dtl[1]['label'] for data_dtl in operational_data], yticklabels=[mission_dtl[1]['label'] for mission_dtl in missions])
    plt.xlabel('Operational Data')
    plt.ylabel('Mission')
    plt.title('Importance of Operational Data for each Mission')
    image_filename = generate_filename("pagerank_analysis_missions", "png")
    plt.savefig(image_filename)
    csv_filename = generate_filename("pagerank_analysis_missions", "csv")
    df = pd.DataFrame(matrix, columns=[data_dtl[1]['label'] for data_dtl in operational_data], index=[mission_dtl[1]['label'] for mission_dtl in missions])
    df.to_csv(csv_filename)

    # Return a JSON response indicating success
    response = {
        "message": "PageRank analysis for all missions completed. Scores are saved.",
        "file_saved": json_filename
    }
    return jsonify(response)



if __name__ == '__main__':
    app.run(debug=False, port = 6868)
