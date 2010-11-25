import random
from math import *
from OpenNero import *
from common import *
from random import *
from constants import *
from TeamAdapt.environment import MazeEnvironment, ContMazeEnvironment
from TeamAdapt.agent import FirstPersonAgent

def count_neurons(constraints):
    """
    Count the number of neurons required to represent the given feature vector
    constraints. For continuous values, scale to a single neuron. For discrete
    values, use (max - min) neurons for a 1-of-N encoding.
    """
    n_neurons = 0
    for i in range(len(constraints)):
        if constraints.discrete(i):
            n_neurons += int(constraints.max(i) - constraints.min(i) + 1)
        else:
            n_neurons += 1
    return n_neurons
    
def input_to_neurons(constraints, input):
    """
    Convert to the ANN coding required to represent the given feature vector. 
    For continuous values, scale to a single neuron. For discrete
    values, use (max - min) neurons for a 1-of-N encoding.
    """
    neurons = []
    for i in range(len(constraints)):
        if constraints.discrete(i):
            section_size = int(constraints.max(i) - constraints.min(i) + 1)
            section = [0 for x in range(section_size)]
            index = int(input[i] - constraints.min(i))
            section[index] = 1
            neurons.extend(section)
        else:
            delta = constraints.max(i) - constraints.min(i)
            neurons.append(neurons[neuron_i] - constraints.min(i)) / delta
    assert(len(neurons) == count_neurons(constraints))
    return neurons

def neurons_to_output(constraints, neurons):
    """
    Convert each continuous value from a neuron output to its range, and each 
    discrete value from it's max-of-N output encoding (where N = Max - Min).
    """
    result = constraints.get_instance()
    neuron_i = 0
    for result_i in range(len(constraints)):
        assert(neuron_i < len(neurons))
        assert(neuron_i >= result_i)
        if constraints.discrete(result_i):
            # section of the neurons coding for this output
            section_size = int(constraints.max(result_i) - constraints.min(result_i) + 1)
            section_values = neurons[neuron_i:(neuron_i + section_size)]
            # the maximally activated neuron in this section
            max_neuron = max(section_values)
            max_index = section_values.index(max_neuron)
            # the result output
            result[result_i] = constraints.min(result_i) + max_index
            neuron_i += section_size
        else:
            delta = constraints.max(result_i) - constraints.min(result_i)
            result[result_i] = constraints.min(i) + neurons[neuron_i] * delta
            neuron_i += 1
    return result

class MazeMod:
    # initializer
    def __init__(self):
        print 'Creating MazeMod'
        self.epsilon = 0.5
        self.speedup = 0.0
        self.shortcircuit = False
        self.environment = None
        self.agent_id = None # the ID of the agent
        self.marker_map = {} # a map of cells and markers so that we don't have more than one per cell
        self.marker_states = {} # states of the marker agents that run for one cell and stop
        self.agent_map = {} # agents active on the map
        self.wall_ids = [] # walls on the map

    def __del__(self):
        print 'Deleting MazeMod'

    def mark_maze(self, r, c, marker):
        """ mark a maze cell with the specified color """
        # remove the previous object, if necessary
        if (r,c) in self.marker_map:
            removeObject(self.marker_map[(r,c)])
        # remember the ID of the marker
        self.marker_map[(r,c)] = addObject(marker, Vector3f( (r+1) * GRID_DX, (c+1) * GRID_DY, -1))

    def mark_maze_blue(self, r, c):
        self.mark_maze(r,c,"data/shapes/cube/BlueCube.xml")

    def mark_maze_green(self, r, c):
        self.mark_maze(r,c,"data/shapes/cube/GreenCube.xml")

    def mark_maze_yellow(self, r, c):
        self.mark_maze(r,c,"data/shapes/cube/YellowCube.xml")

    def mark_maze_white(self, r, c):
        self.mark_maze(r,c,"data/shapes/cube/WhiteCube.xml")

    def unmark_maze_agent(self, r, c):
        """ mark a maze cell with the specified color """
        # remove the previous object, if necessary
        if (r,c) in self.agent_map:
            removeObject(self.agent_map[(r,c)])
            del self.marker_states[self.agent_map[(r,c)]]
            del self.agent_map[(r,c)]

    def mark_maze_agent(self, agent, r1, c1, r2, c2):
        """ mark a maze cell with the specified color """
        # remove the previous object, if necessary
        self.unmark_maze_agent(r2,c2)
        # add a new marker object
        agent_id = addObject(agent, Vector3f( (r1+1) * GRID_DX, (c1+1) * GRID_DY, 2) )
        self.marker_states[agent_id] = ((r1, c1), (r2, c2))
        self.agent_map[(r2,c2)] = agent_id

    # add a set of coordinate axes
    def addAxes(self):
        getSimContext().addAxes()

    def add_maze(self):
        """Add a randomly generated maze"""
        if self.environment:
            print "ERROR: Environment already created"
            return
        self.set_environment(MazeEnvironment())

    def set_environment(self,env):
        self.environment = env
        self.environment.epsilon = self.epsilon
        self.environment.speedup = self.speedup
        self.environment.shortcircuit = self.shortcircuit
        for id in self.wall_ids: # delete the walls
            removeObject(id)
        del self.wall_ids[:] # clear the ids
        set_environment(env)
        for ((r1, c1), (r2, c2)) in env.maze.walls:
            (x1,y1) = env.maze.rc2xy(r1,c1)
            (x2,y2) = env.maze.rc2xy(r2,c2)
            pos = Vector3f( (x1 + x2) / 2, (y1 + y2) / 2, 2.5 )
            z_rotation = 0
            if r1 != r2:
                z_rotation = 90
            self.wall_ids.append(addObject(WALL_TEMPLATE, pos, Vector3f(0, 0, z_rotation), type=OBSTACLE_MASK))
        # world boundaries
        for i in range(1,COLS+1):
            self.wall_ids.append(addObject(WALL_TEMPLATE, Vector3f(GRID_DX/2, i * GRID_DY, 2), Vector3f(0, 0, 90), type=OBSTACLE_MASK ))
            self.wall_ids.append(addObject(WALL_TEMPLATE, Vector3f(i * GRID_DX, GRID_DY/2, 2), Vector3f(0, 0, 0), type=OBSTACLE_MASK ))
            self.wall_ids.append(addObject(WALL_TEMPLATE, Vector3f(i * GRID_DX, COLS * GRID_DY + GRID_DY/2, 2), Vector3f(0, 0, 0), type=OBSTACLE_MASK ))
            self.wall_ids.append(addObject(WALL_TEMPLATE, Vector3f(ROWS * GRID_DX + GRID_DX/2, i * GRID_DY, 2), Vector3f(0, 0, 90), type=OBSTACLE_MASK ))
        # goal (red cube)
        self.wall_ids.append(addObject("data/shapes/cube/RedCube.xml", Vector3f(4 * GRID_DX, 8 * GRID_DY, 5), Vector3f(45,45,45)))

    def reset_maze(self):
        """ reset the maze by removing the markers and starting the AI """
        # remove the marker blocks
        for id in self.marker_map.values():
            removeObject(id)
        self.marker_map = {}
        for id in self.agent_map.values():
            removeObject(id)
        self.agent_map = {}
        # remove the agent
        if self.agent_id is not None:
            removeObject(self.agent_id)
        self.agent_id = None
        reset_ai()

    def start_dfs(self):
        """ start the depth first search demo """
        disable_ai()
        self.reset_maze()
        if self.environment.__class__.__name__ != 'MazeEnvironment':
            self.set_environment(MazeEnvironment())
        self.agent_id = addObject("data/shapes/character/SydneyDFS.xml", Vector3f(GRID_DX, GRID_DY, 2), type=AGENT_MASK )
        getSimContext().setObjectAnimation(self.agent_id, 'run')
        enable_ai()

    def start_astar(self):
        """ start the A* search demo """
        disable_ai()
        self.reset_maze()
        if self.environment.__class__.__name__ != 'MazeEnvironment':
            self.set_environment(MazeEnvironment())
        self.agent_id = addObject("data/shapes/character/SydneyAStar.xml", Vector3f(GRID_DX, GRID_DY, 2), type=AGENT_MASK )
        getSimContext().setObjectAnimation(self.agent_id, 'run')
        enable_ai()

    def start_astar2(self):
        """ start the A* search demo with teleporting agents """
        disable_ai()
        self.reset_maze()
        if self.environment.__class__.__name__ != 'MazeEnvironment':
            self.set_environment(MazeEnvironment())
        self.agent_id = addObject("data/shapes/character/SydneyAStar2.xml", Vector3f(GRID_DX, GRID_DY, 2), type=AGENT_MASK )
        getSimContext().setObjectAnimation(self.agent_id, 'run')
        enable_ai()

    def start_astar3(self):
        """ start the A* search demo with teleporting agents """
        disable_ai()
        self.reset_maze()
        if self.environment.__class__.__name__ != 'MazeEnvironment':
            self.set_environment(MazeEnvironment())
        self.agent_id = addObject("data/shapes/character/SydneyAStar3.xml", Vector3f(GRID_DX, GRID_DY, 2), type=AGENT_MASK )
        getSimContext().setObjectAnimation(self.agent_id, 'run')
        enable_ai()

    def start_fps(self):
        """ start the FPS navigation demo for the natural language experiment """
        disable_ai()
        self.reset_maze()
        if self.environment.__class__.__name__ != 'ContMazeEnvironment':
            self.set_environment(ContMazeEnvironment())
        self.agent_id = addObject("data/shapes/character/SydneyFPS.xml", Vector3f(GRID_DX, GRID_DY, 2), type=AGENT_MASK )
        enable_ai()

    def start_random(self):
        """ start the rtneat learning demo """
        disable_ai()
        self.reset_maze()
        # ensure that we have the environment ready
        if self.environment.__class__.__name__ != 'MazeEnvironment':
            self.set_environment(MazeEnvironment())
        enable_ai()
        self.agent_id = addObject("data/shapes/character/SydneyRandom.xml",Vector3f(GRID_DX, GRID_DY, 2), type=AGENT_MASK )

    def start_rtneat(self):
        """ start the rtneat learning demo """
        disable_ai()
        self.reset_maze()
        if self.environment.__class__.__name__ != 'MazeEnvironment':
            self.set_environment(MazeEnvironment())
        agent_info = get_environment().agent_info


        self.environment.agentList = {}
        # Create an rtNEAT object appropriate for the environment
        pop_size = 50
        pop_on_field_size = 10
        barb_on_field_size = 3
        city_on_field_size = 3

        # Establish the number of inputs and outputs
        # We use 1 neuron for each continuous value, and N neurons for 1-of-N
        # coding for discrete variables

        # For inputs, the number of neurons depends on the sensor constraints
        n_inputs = len(agent_info.sensors)+1
        
        #for standard mapping
        #count_neurons(agent_info.sensors)

        # For outputs, the number of neurons depends on the action constraints

        #TODO: =TEN
        #TODO: remake fitness
        #TODO: fix sensors
        #TODO: stop creating avoiders

        n_outputs = 10

        #for standard mapping
        #count_neurons(agent_info.actions)
        
        print 'RTNEAT, inputs: %d, outputs: %d' % (n_inputs, n_outputs)

        # create the rtneat object that will manage the population of agents
        rtneat = RTNEAT("data/ai/neat-params.dat", n_inputs, n_outputs, pop_size, 1.0)
        set_ai("neat",rtneat)
        enable_ai()
#        self.place_legions_hardCoded()
        self.place_legions(pop_on_field_size)
        #self.place_cities(city_on_field_size)
#        self.place_avoiders()
        self.place_barbarians(barb_on_field_size)

    def place_cities(self, number):

      #NOT randomly placed
      posDict = {}
      posDict[0] = (4,7)
      posDict[1] = (7,5)
      posDict[2] = (1,3)

      for key in posDict.iterkeys():

        r = posDict[key][0]
        dx = r * GRID_DX
        c = posDict[key][1]
        dy = c * GRID_DY
        city = addObject("data/shapes/objects/city.xml",Vector3f(dx, dy, 2), type=AGENT_MASK)

        state = self.environment.get_object_state(city)
        state.rc = (r,c)
        state.agentType = 2

    def place_avoiders(self):

      #NOT randomly placed
      posDict = {}
      posDict[0] = (3,0)
      posDict[1] = (4,0)

      for key in posDict.iterkeys():

        r = posDict[key][0]
        dx = r * GRID_DX
        c = posDict[key][1]
        dy = c * GRID_DY
        city = addObject("data/shapes/character/SydneyAvoider.xml",Vector3f(dx, dy, 2), type=AGENT_MASK)

        state = self.environment.get_state(city)
        state.rc = (r,c)
        state.agentType = 0
        print str(self.environment.states[city].rc)
        print "done creating avoider"

    def place_legions_hardCoded(self):

      #NOT randomly placed
      posDict = {}
      posDict[0] = (4,1)
      posDict[1] = (4,7)

      for key in posDict.iterkeys():

        r = posDict[key][0]
        dx = r * GRID_DX
        c = posDict[key][1]
        dy = c * GRID_DY
        city = addObject("data/shapes/character/SydneyRTNEAT.xml",Vector3f(dx, dy, 2), type=AGENT_MASK)
        self.agent_map[(0,key)] = city

        state = self.environment.get_state(city)
        state.rc = (r,c)
        state.agentType = 0
        print str(self.environment.states[city].rc)
        print "done creating legion"

    def place_legions(self, number):

      for i in range(0, number):
        placed = False
        #pick random cells, test if valid, repeat if not
        while(placed == False):

          r = randint(1,ROWS-1)
          dx = r * GRID_DX
          c = randint(1,COLS-1)
          dy = c * GRID_DY

          #is the cell occupied by a barbarian/legion?
          print "creating legion"
          if self.environment.cell_occupied(r,c,0) == 0 and self.environment.cell_occupied(r,c,1) == 0:
            self.agent_map[(0,i)] = addObject("data/shapes/character/SydneyRTNEAT.xml",Vector3f(dx, dy, 2), type=AGENT_MASK)
            
            
            state = self.environment.get_state(self.agent_map[(0,i)])
            state.rc = (r,c)
            state.agentType = 0
            self.environment.lastAgent = self.agent_map[(0,i)]
            print str(self.environment.states[self.agent_map[(0,i)]].rc)
#            self.environment.agentList[self.agent_map[(0,i)]] = (r,c,0)
#            self.environment.states[agent]
            placed = True
            print "done creating legion"

    def place_barbarians(self, number):

      for i in range(0, number):
        placed = False
        #pick random cells, test if valid, repeat if not
        while(placed == False):

          r = randint(1,ROWS)
          dx = r * GRID_DX
          c =  randint(1,COLS)
          dy = c * GRID_DY
          #is the cell occupied by a barbarian/legion?
          if self.environment.cell_occupied(r,c,0) == 0 and self.environment.cell_occupied(r,c,1) == 0:
            self.agent_map[(1,i)] = addObject("data/shapes/character/SydneyBarbarian.xml",Vector3f(dx, dy, 2), type=AGENT_MASK)
            state = self.environment.get_state(self.agent_map[(1,i)])
            state.rc = (r,c)
            state.agentType = 1
            self.environment.lastAgent = self.agent_map[(1,i)]
            print str(self.environment.states[self.agent_map[(1,i)]].rc)
#            self.environment.agentList[self.agent_map[(0,i)]] = (r,c,0)
            placed = True
            print "done"
        



    def start_sarsa(self):
        """ start the rtneat learning demo """
        disable_ai()
        self.reset_maze()
        if self.environment.__class__.__name__ != 'MazeEnvironment':
            self.set_environment(MazeEnvironment())
        self.agent_id = addObject("data/shapes/character/SydneySarsa.xml", Vector3f(GRID_DX, GRID_DY, 2), type=AGENT_MASK )
        enable_ai()

    def start_qlearning(self):
        """ start the q-learning demo """
        disable_ai()
        self.reset_maze()
        if self.environment.__class__.__name__ != 'MazeEnvironment':
            self.set_environment(MazeEnvironment())
        self.agent_id = addObject("data/shapes/character/SydneyQLearning.xml", Vector3f(GRID_DX, GRID_DY, 2), type=AGENT_MASK )
        enable_ai()

    def control_fps(self,key):
        FirstPersonAgent.key_pressed = key

    def set_epsilon(self, epsilon):
        self.epsilon = epsilon
        print 'Epsilon set to', self.epsilon
        if self.environment:
            self.environment.epsilon = epsilon
            
    def set_speedup(self, speedup):
        self.speedup = speedup
        print 'Speedup set to', self.speedup
        if self.environment:
            self.environment.speedup = speedup
    
    def set_shortcircuit(self, shortcircuit):
        self.shortcircuit = shortcircuit
        print 'Short-circuit set to', self.shortcircuit
        if self.environment:
            self.environment.shortcircuit = shortcircuit

gMod = None

def delMod():
    global gMod
    gMod = None

def getMod():
    global gMod
    if not gMod:
        gMod = MazeMod()
    return gMod
