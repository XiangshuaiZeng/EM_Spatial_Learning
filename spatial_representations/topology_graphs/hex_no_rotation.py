import PyQt5 as qt
import pyqtgraph as qg
import pyqtgraph.functions
import numpy as np
import gym
import time
from scipy.spatial import Delaunay

from PyQt5 import QtGui
from .misc.topology_node import TopologyNode
from .misc.cog_arrow import CogArrow

from cobel.spatial_representations.spatial_representation import SpatialRepresentation


class HexTopologyGraphNoRotation(SpatialRepresentation):
    
    def __init__(self, modules, graph_info):
        
        # call the base class init
        super(HexTopologyGraphNoRotation,self).__init__()
        
        
        # normally, the topology graph is not shown in gui_parent
        self.visual_output=False
        self.gui_parent=None
        
        
        #store the graph parameters
        self.graph_info=graph_info
        
        # extract the world module
        self.modules=modules
        
        # the world module is required here
        world_module=modules['world']
        
        # get the limits of the given environment
        self.world_limits = world_module.getLimits()
        print("World limits are : ", self.world_limits)
        # retrieve all boundary information from the environment
        self.world_nodes, self.world_edges = world_module.getWallGraph()
        
            
        
        # inherent definitions for the topology graph
        
        # this is the node corresponding to the robot's actual position
        self.currentNode=-1
        # this is the node corresponding to the robot's next position
        self.nextNode=-1
        # this list of topologyNode[s] stores all nodes of the graph
        self.nodes=[]
        # this list of [int,int]-entries defines all edges (unique) which make up the graph's connectivity
        self.edges=[]
        
        
        
        
        self.cliqueSize=graph_info['cliqueSize']
        self.nodeCountXDomain=graph_info['nodesXDomain']
        self.nodeCountYDomain=graph_info['nodesYDomain']
        self.gridPerimeter=graph_info['gridPerimeter']

        xDomain=np.linspace(self.gridPerimeter[0],self.gridPerimeter[1],self.nodeCountXDomain)
        yDomain=np.linspace(self.gridPerimeter[2],self.gridPerimeter[3],self.nodeCountYDomain)
        
        period = xDomain[1] - xDomain[0]
        grid_points = np.array([[x, y] for y in yDomain for x in xDomain])
        shift_indices =  []
        
        for y in yDomain[1::2] :
            shift_indices.append(np.where(grid_points[:,1]==y)[0])

        s = np.ravel(shift_indices)
            
        for idx in s:
            grid_points[idx][0] += period/2 

        del_indices = np.where(grid_points[:,0] > self.gridPerimeter[1])[0]
        grid_points = np.delete(grid_points,del_indices,0)
        
        self.mesh = Delaunay(grid_points,qhull_options='Qt Qbb Qc')
        self.mesh_points = self.mesh.points
        self.mesh_elements = self.mesh.simplices
        
        ne = self.mesh_elements.shape[0]
        edges = np.array([self.mesh_elements[:,0], self.mesh_elements[:,1], 
                            self.mesh_elements[:,1], self.mesh_elements[:,2],
                            self.mesh_elements[:,2], self.mesh_elements[:,0]]).T.reshape(3*ne,2)
        edges = np.sort(edges)
        
        edges = np.unique(edges,axis=0)

        # transfer the node points into the self.nodes list
        indexCounter=0
        for p in self.mesh_points:
            # create the corresponding node, where i is the running index of the mesh_points/corresponding nodes
            node=TopologyNode(indexCounter,p[0],p[1])
            self.nodes=self.nodes+[node]
            indexCounter+=1
        
        
        # fill in the self.edges list from the edges information
        for e in edges:
            self.edges=self.edges+[[int(e[0]),int(e[1])]]
            
            
            
        # define a dedicated 'noneNode' that acts as a placeholder for neighborhood construction
        noneNode=TopologyNode(-1,0.0,0.0)
        
        # comstruct the neighborhoods of each node in the graph
        for edge in self.edges:
            # first edge node
            a=self.nodes[int(edge[0])]
            # second edge node
            b=self.nodes[int(edge[1])]
            # add node a to the neighborhood of node b, and vice versa
            a.neighbors=a.neighbors+[b]
            b.neighbors=b.neighbors+[a]
        
        
        # it is possible that a node does not have the maximum possible number of neighbors, to stay consistent in RL, fill up the neighborhood
        # with noneNode[s]:
        
        def calculateAngle(node_info, neighbor_info) : 
            ref = np.array([node_info.x,node_info.y-1])
            node = np.array([node_info.x,node_info.y])
            neighbor = np.array([neighbor_info.x,neighbor_info.y])
            ref_vector = ref - node
            vector = neighbor - node
        
            cos_ang = np.dot(ref_vector, vector) / (np.linalg.norm(ref_vector) * np.linalg.norm(vector))
            det = ref_vector[0] * vector[1] - ref_vector[1] * vector[0]
            angle = np.arccos(cos_ang)
            if det>0 :
                return 360 - np.degrees(angle)
            else : 
                return np.degrees(angle)
            
        def sortGraph(node_info) :
            n_sorted_index = np.full(6,noneNode)
            for n in node_info.neighbors : 
                a = calculateAngle(node_info,n)
                if 0 <= a < 89 :
                    n_sorted_index[0] = n
                if 89 < a < 149 :
                    n_sorted_index[1] = n
                if 149 < a < 209 :
                    n_sorted_index[2] = n
                if 209 < a < 269 :
                    n_sorted_index[3] = n
                if 269 < a < 329 :
                    n_sorted_index[4] = n
                if 329 < a < 360 :
                    n_sorted_index[5] = n
                    
            node_info.neighbors = n_sorted_index
            
        for node in self.nodes:
            sortGraph(node)

        for nodeIndex in self.graph_info['startNodes']:
            self.nodes[nodeIndex].startNode=True
            
        # assign goal nodes
        for nodeIndex in self.graph_info['goalNodes']:
            self.nodes[nodeIndex].goalNode=True

        self.sample_state_space()
        



    def set_visual_debugging(self,visual_output,gui_parent):
        
        self.gui_parent=gui_parent
        self.visual_output=visual_output
        self.initVisualElements()
        



    def initVisualElements(self):
        # do basic visualization
        # iff visualOutput is set to True!
        if self.visual_output:

            # add the graph plot to the GUI widget
            self.plot = self.gui_parent.addPlot(title='Topology graph')
            # set extension of the plot, lock aspect ratio
            self.plot.setXRange( self.world_limits[0,0], self.world_limits[0,1] )
            self.plot.setYRange( self.world_limits[1,0], self.world_limits[1,1] )
            self.plot.setAspectLocked()

            
           
                
            # set up indicator arrows for each node, except the goal node, and all nodes in active shock zones iff shock zones exist
            for node in self.nodes:
                if not node.goalNode:
                    node.qIndicator=CogArrow(angle=0.0,headLen=20.0,tipAngle=25.0,tailLen=0.0,brush=(255,255,0))
                    self.plot.addItem(node.qIndicator)
            
            
            
            
                
            # overlay the world's perimeter
            self.perimeterGraph=qg.GraphItem()
            self.plot.addItem(self.perimeterGraph)
            
            self.perimeterGraph.setData(pos=np.array(self.world_nodes),adj=np.array(self.world_edges),brush=(128,128,128))
            
            
            
            # overlay the topology graph
            self.topologyGraph=qg.GraphItem()
            self.plot.addItem(self.topologyGraph)
            
            # set up a brushes array for visualization of the nodes
            # normal nodes are grey
            symbolBrushes=[qg.mkBrush(color=(128,128,128))]*len(self.nodes)
            
            
            # set colors of normal and goal nodes
            for node in self.nodes:
                
                # start nodes are green
                if node.startNode:
                    symbolBrushes[node.index]=qg.mkBrush(color=(0,255,0))
            
                # goal node is red
                if node.goalNode:
                    symbolBrushes[node.index]=qg.mkBrush(color=(255,0,0))
        
            # construct appropriate arrays from the self.nodes and the self.edges information
            tempNodes=[]
            tempEdges=[]
            for node in self.nodes:
                tempNodes=tempNodes+[[node.x,node.y]]
                
            for edge in self.edges:
                tempEdges=tempEdges+[[edge[0],edge[1]]]

            self.topologyGraph.setData(pos=np.array(tempNodes),adj=np.array(tempEdges),symbolBrush=symbolBrushes)
            
            
            # eventually, overlay robot marker
            self.posMarker=CogArrow(angle=0.0,headLen=20.0,tipAngle=25.0,tailLen=0.0,brush=(255,0,0))
            self.plot.addItem(self.posMarker)
            # initial position to center, this has to be worked over later!
            self.posMarker.setData(0.0,0.0,0.0)
            
        
    def updateVisualElements(self):
        
                            
            
            
            # overlay the policy arrows
            
            if self.visual_output:
                # for all nodes in the topology graph
                for node in self.nodes:
                    
                    
                    # query the model at each node's position
                    # only for valid nodes!
                    if node.index!=-1:
                        observation=self.state_space[node.index]
                        data=np.array([[observation]])
                        # get the q-values at the queried node's position
                        q_values = self.rlAgent.agent.model.predict_on_batch(data)[0]
                        
                        # find all neighbors that are actually valid (index != -1)
                        validIndex=0
                        for n_index in range(len(node.neighbors)):
                            if node.neighbors[n_index].index!=-1:
                                validIndex=n_index
                        
                        # find the index of the neighboring node that is 'pointed to' by the highest q-value, AND is valid!
                        maxNeighNode=node.neighbors[np.argmax(q_values[0:validIndex+1])]
                        # find the direction of the selected neighboring node
                        # to node: maxNeighNode
                        toNode=np.array([maxNeighNode.x,maxNeighNode.y])
                        # from node: node
                        fromNode=np.array([node.x,node.y])
                        # the difference vector between to and from
                        vec=toNode-fromNode
                        # normalize the direction vector
                        l=np.linalg.norm(vec)
                        vec=vec/l
                        # make the corresponding indicator point in the direction of the difference vector
                        node.qIndicator.setData(node.x,node.y,np.rad2deg(np.arctan2(vec[1],vec[0])))  

    # This function updates the visual depiction of the agent(robot).
    # 
    # pose: the agent's pose to visualize
    def updateRobotPose(self,pose):
        if self.visual_output:
            self.posMarker.setData(pose[0],pose[1],np.rad2deg(np.arctan2(pose[3],pose[2])))



    def sample_state_space(self):
        
        # the world module is required here
        world_module=self.modules['world']
        
        # the observation module is required here
        observation_module=self.modules['observation']
        
        # In this specific topology graph, a state is an image sampled from a specific node of the graph. There
        # is no rotation, so one image per node is sufficient.
        
        self.state_space=[]
        for node_index in range(len(self.nodes)):
            node=self.nodes[node_index]
            # set agent to x/y-position of 'node'
            world_module.step_simulation_without_physics(node.x,node.y,90.0)
            world_module.step_simulation_without_physics(node.x,node.y,90.0)
            observation_module.update()
            observation=observation_module.observation
            self.state_space+=[observation]
        return


    def generate_behavior_from_action(self,action):
        
        nextNodePos=np.array([0.0,0.0])
        callback_value=dict()
        
        # if a standard action is performed
        if action!='reset':

            previousNode=self.modules['spatial_representation'].currentNode
            # with action given, the next node can be computed
            self.modules['spatial_representation'].nextNode=self.modules['spatial_representation'].nodes[self.modules['spatial_representation'].currentNode].neighbors[action].index
            
            # array to store the next node's coordinates
                
            if self.modules['spatial_representation'].nextNode!=-1:
                # compute the next node's coordinates
                nextNodePos=np.array([self.modules['spatial_representation'].nodes[self.modules['spatial_representation'].nextNode].x,self.modules['spatial_representation'].nodes[self.modules['spatial_representation'].nextNode].y])
            else:
                # if the next node corresponds to an invalid node, the agent stays in place
                self.modules['spatial_representation'].nextNode=self.modules['spatial_representation'].currentNode
                # prevent the agent from starting any motion pattern
                self.modules['world'].goalReached=True
                nextNodePos=np.array([self.modules['spatial_representation'].nodes[self.modules['spatial_representation'].currentNode].x,self.modules['spatial_representation'].nodes[self.modules['spatial_representation'].currentNode].y])
            
            
            
            # here, next node is already set and the current node is set to this next node.
            callback_value['currentNode']=self.nodes[self.nextNode]
            
            
        # if a reset is performed
        else:
            # a random node is chosen to place the agent at (this node MUST NOT be the global goal node!)
            nextNode=-1
            while True:
                nrNodes=len(self.modules['spatial_representation'].nodes)
                nextNode=np.random.random_integers(0,nrNodes-1)
                if self.modules['spatial_representation'].nodes[nextNode].startNode:
                    break
            
            nextNodePos=np.array([self.modules['spatial_representation'].nodes[nextNode].x,self.modules['spatial_representation'].nodes[nextNode].y])
            self.modules['spatial_representation'].nextNode=nextNode
            
        # actually move the robot to the node
        self.modules['world'].actuateRobot(np.array([nextNodePos[0],nextNodePos[1],90.0])) 
        self.modules['world'].actuateRobot(np.array([nextNodePos[0],nextNodePos[1],90.0])) 
        
        
        # make the current node the one the agent travelled to
        self.modules['spatial_representation'].currentNode=self.modules['spatial_representation'].nextNode
        
        self.modules['observation'].update()
        self.modules['spatial_representation'].updateRobotPose([nextNodePos[0],nextNodePos[1],0.0,1.0])
        
        # if possible try to update the visual debugging display
        if hasattr(qt.QtGui, 'QApplication'):
            if qt.QtGui.QApplication.instance() is not None:
                qt.QtGui.QApplication.instance().processEvents()
        else:
            if qt.QtWidgets.QApplication.instance() is not None:
                qt.QtWidgets.QApplication.instance().processEvents()

        return callback_value

    def get_action_space(self):
        # for this spatial representation type, the clique size of the topology graph defines the action space
        return gym.spaces.Discrete(self.cliqueSize)

class HexTopologyAllocentric(HexTopologyGraphNoRotation) : 
    
    def get_action_space(self) : 
        """Actions are allocentric directions 
        plus two rotations 
        """
        return gym.spaces.Discrete(self.cliqueSize + 2)
    
    def updateRobotPose(self, pose, angle) :
        if self.visual_output:
            self.posMarker.setData(pose[0],pose[1],np.deg2rad(angle))

    def updateVisualElements(self) :
        pass
    
    def generate_behavior_from_action(self, action) :
        
        nextNodePos=np.array([0.0,0.0])
        callback_value=dict()

        if action!='reset':
            previousNode=self.modules['spatial_representation'].currentNode
            if action == 6 :
                self.modules['world'].set_angle(self.modules['world'].angle + 60)
                self.modules['spatial_representation'].nextNode = previousNode

            if action == 7 :
                self.modules['world'].set_angle(self.modules['world'].angle - 60)
                self.modules['spatial_representation'].nextNode = previousNode
            
            if action < 6 :
                self.modules['spatial_representation'].nextNode = self.modules['spatial_representation'].nodes[self.modules['spatial_representation'].currentNode].neighbors[action].index

                if self.modules['spatial_representation'].nextNode!=-1:
                    nextNodePos=np.array([self.modules['spatial_representation'].nodes[self.modules['spatial_representation'].nextNode].x,self.modules['spatial_representation'].nodes[self.modules['spatial_representation'].nextNode].y])
                else:
                    self.modules['spatial_representation'].nextNode=self.modules['spatial_representation'].currentNode
                    self.modules['world'].goalReached=True
                    nextNodePos=np.array([self.modules['spatial_representation'].nodes[self.modules['spatial_representation'].currentNode].x,self.modules['spatial_representation'].nodes[self.modules['spatial_representation'].currentNode].y])
                
            callback_value['currentNode']=self.nodes[self.nextNode]
                
        else:
            nextNode=-1
            while True:
                nrNodes=len(self.modules['spatial_representation'].nodes)
                nextNode=np.random.random_integers(0,nrNodes-1)
                if self.modules['spatial_representation'].nodes[nextNode].startNode:
                    break
            
            nextNodePos=np.array([self.modules['spatial_representation'].nodes[nextNode].x,self.modules['spatial_representation'].nodes[nextNode].y])
            self.modules['spatial_representation'].nextNode=nextNode
                
            # actually move the robot to the node
        self.modules['world'].actuateRobot(np.array([nextNodePos[0],nextNodePos[1],self.modules['world'].angle])) 
        self.modules['world'].actuateRobot(np.array([nextNodePos[0],nextNodePos[1],self.modules['world'].angle])) 
    
    
    # make the current node the one the agent travelled to
        self.modules['spatial_representation'].currentNode=self.modules['spatial_representation'].nextNode
        
        self.modules['observation'].update()
        self.modules['spatial_representation'].updateRobotPose([nextNodePos[0],nextNodePos[1]],self.modules['world'].angle)
        
        # if possible try to update the visual debugging display
        if qt.QtGui.QApplication.instance() is not None:
            qt.QtGui.QApplication.instance().processEvents()
        
        return callback_value
    
    def sample_state_space(self):
        
        # the world module is required here
        world_module=self.modules['world']
        
        # the observation module is required here
        observation_module=self.modules['observation']
        
        # In this specific topology graph, a state is an image sampled from a specific node of the graph. There
        # is no rotation, so one image per node is sufficient.
        
        self.state_space=[]
        for node_index in range(len(self.nodes)):
            node=self.nodes[node_index]
            # set agent to x/y-position of 'node'
            world_module.step_simulation_without_physics(node.x,node.y,self.modules['world'].angle)
            world_module.step_simulation_without_physics(node.x,node.y,self.modules['world'].angle)
            observation_module.update()
            observation=observation_module.observation
            self.state_space+=[observation]
        return

