import os
import sys
import csv
import torch
import random as rand
import numpy as np
import matplotlib.pyplot as plt
import gymnasium as gym

# Add project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import project modules
from utils.individual import Individual, Models
from evolutionary.functions import norm_fitness_of_generation, roulette_wheel_selection
from controller.fc import FC
from controller.cpg_fc import CPG_FC
from controller.rbfn_fc import RBFN_FC
from controller.cpg_rbfn import CPG_RBFN

class NeuroEvolution():
    """Class for all the Neuro Evolutionary functions"""

    def __init__(self, model_type: str, env_type: str, fixed_centres: bool=False, generations: int=100, max_steps: int=1000,
                 gen_size: int=10, elite_size: int=10, load_elite: bool=False, alt_cpgs: bool=False, add_noise: bool=False, mean: float=1.0, std: float=0.001):
        """Initialize the Neuro Evolutionary parameters"""

        # Arguments
        self.model_type = model_type
        self.env_type = env_type
        self.fixed_centres = fixed_centres
        self.alt_cpgs = alt_cpgs
        self.add_noise = add_noise
        self.generations = generations
        self.max_steps = max_steps
        self.gen_size = gen_size
        self.elite_size = elite_size
        self.load_elite = load_elite
        self.mean = mean
        self.std = std

        # Path for saving/loading elite
        self.elite_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", env_type, model_type, "not_fixed")

        #Set new path to load files from if fixed centers are selected
        if self.fixed_centres:
            self.elite_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", env_type, model_type, "fixed")

        elif self.alt_cpgs and self.add_noise:
            self.elite_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", env_type, model_type, "noisy_alt_cpgs")

        elif self.alt_cpgs:
            self.elite_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", env_type, model_type, "alt_cpgs")

        elif self.add_noise:
            self.elite_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", env_type, model_type, "add_noise")

        # Create the environment
        self.env = gym.make(self.env_type)

        # Fixed Parameters
        self.in_size = self.env.observation_space.shape[0]
        self.out_size = self.env.action_space.shape[0]

        ## Model specific parameters
        # FC & CPG-FC model
        self.fc_h1 = 30
        self.fc_h2 = 30
        # CPG-RBFN model
        self.rbfn_units = 20

        # Define the models
        self.models = Models()

        # Initialize the generation
        self.generation = self.get_gen(is_init=True)

        # Reward history
        self.reward_history = []
        self.best_per_gen = []
        self.mean_per_gen = []
        self.mean_error_per_gen = []

    def get_model(self):
        #Get model
        model = None
        match self.model_type:
            case self.models.CPG_RBFN_MODEL:
                model = CPG_RBFN(rbf_size=self.rbfn_units, out_size=self.out_size, fixed_centers=self.fixed_centres, alt_cpgs=self.alt_cpgs, add_noise=self.add_noise)
            case self.models.RBFN_FC_MODEL:
                model = RBFN_FC(self.in_size, self.rbfn_units, self.out_size)
            case self.models.CPG_FC_MODEL:
                model = CPG_FC(self.fc_h1, self.fc_h2, self.out_size)
            case self.models.FC_MODEL:
                model = FC(self.in_size, self.fc_h1, self.fc_h2, self.out_size)
        return model


    def get_gen(self, is_init: bool=False):
        """Create a new generation"""

        generation = []
        elite = []

        #Load elite if this is the initial generation
        if self.load_elite and is_init:

            print("Loading elites..")

            #Load files
            for i in range(self.elite_size):
                model = self.get_model()
                model.load_state_dict(torch.load(f"{self.elite_path}/model{i}.pt"))
                elite.append(Individual(model))

            # Add elite if any
            for i in range(len(elite)):
                generation.append(elite[i])

        #Add new individuals
        for _ in range(self.gen_size-len(elite)):
            #Set model
            generation.append(Individual(self.get_model()))

        return generation

    def run_gen(self, generation):
        """Run every Individual in a generation through the environment"""

        # Run each individual
        for individual in generation:

            # Reset the environment, get initial state
            state, _ = self.env.reset()

            # Run for max steps or until terminated/truncated
            for _ in range(self.max_steps):

                # Choose action based on model type
                action = None
                match self.model_type:
                    case 'CPG-RBFN' | 'CPG-FC':
                        action = individual.choose_action()
                    case 'FC' | 'RBFN-FC':
                        x = np.array(state, dtype=np.float32)
                        x = torch.tensor(x, dtype=torch.float32)
                        action = individual.choose_action(x)

                # Take action in environment
                state, reward, terminated, truncated, _ = self.env.step(action)

                # Update fitness
                individual.fitness += reward

                # Break if terminated or truncated
                if terminated or truncated:
                    break

            # Reset CPG if present
            if self.model_type == self.models.CPG_FC_MODEL or self.model_type == self.models.CPG_RBFN_MODEL:
                individual.model.cpg.reset()


    def mutate(self, params: torch.tensor, mutations: int = -1):
        """Mutate the parameters of an Individual
        -1 means mutate all parameters, otherwise mutate a random number of parameters"""

        # Mutate all parameters
        if mutations == -1:
            param_mutations = np.random.normal(self.mean, self.std, params.shape)
            param_mutations = torch.from_numpy(param_mutations).float()
            params = torch.mul(params, param_mutations)

        # Mutate a percentage of parameters
        else:
            for _ in range(mutations):
                params[rand.randrange(len(params))] += np.random.normal(self.mean, self.std)

        return params

    def run(self, verbose: bool = False):
        """Run the algorithm"""
        # Iterate generations
        for gen_count in range(self.generations):

            # Run the initial generation
            self.run_gen(self.generation)

            #Get fitness of current generation
            fitness_of_generation = norm_fitness_of_generation(self.generation)

            #Breed gen_size children
            children = []
            for _ in range(0, self.gen_size):
                # Select parents for breeding through roulette wheel selection
                parent = self.generation[roulette_wheel_selection(fitness_of_generation)]

                #Mutation
                mutate_percent = 0.1
                mutations = int(parent.model.dim * mutate_percent)

                child = Individual(self.get_model())
                child.model.set_params(self.mutate(parent.model.get_params(), mutations=mutations))

                children.append(child)

            # Run the children
            self.run_gen(children)

            # Add the children to the generation
            self.generation.extend(children)

            # Select the best solutions up to gen_size
            self.generation.sort(key=lambda x: x.fitness, reverse=True)
            self.generation = self.generation[:self.gen_size]

            # Add fitness statistics
            self.reward_history.append([individual.fitness for individual in self.generation])
            self.best_per_gen.append(np.max(self.reward_history[-1]))
            self.mean_per_gen.append(np.mean(self.reward_history[-1]))
            self.mean_error_per_gen.append(np.std(self.reward_history[-1]) / np.sqrt(self.generations + 1))

            #Reset fitness
            for i in self.generation:
                i.fitness = 0

            # Print progress if verbose
            if verbose:
                print(f"Generation {gen_count+1}: Best Reward {self.best_per_gen[-1]}")

    def save(self, path: str):
        """Save reward history to csv and models of the last generation"""

        # Create directory if it doesn't exist
        if not os.path.exists(path):
            os.makedirs(path)

        # Save reward history to csv
        with open(os.path.join(path, "reward_history.csv"), "w") as f:
            writer = csv.writer(f)
            writer.writerow("Reward History")
            writer.writerow(self.reward_history)
            writer.writerow("Best Reward per Generation")
            writer.writerow(self.best_per_gen)
            writer.writerow("Mean Reward per Generation")
            writer.writerow(self.mean_per_gen)
            writer.writerow("Mean Reward Error per Generation")
            writer.writerow(self.mean_error_per_gen)

        # Save models of the last generation
        for i, indv in enumerate(self.generation):
            torch.save(indv.model.state_dict(), os.path.join(path, f"model{i}.pt"))

    def get_plots(self, path:str, is_show: bool = False):
        """Plot the reward history statistics and save the plots"""

        # Plot reward of every individual in every generation
        plt.figure("Reward History All")
        plt.title("Reward History All")
        plt.xlabel("Generation")
        plt.ylabel("Reward")
        for i, rewards in enumerate(self.reward_history):
            plt.scatter([i] * len(rewards), rewards, s=1)
        plt.savefig(os.path.join(path, "reward_history_all.png"))

        # Plot best reward of every generation
        plt.figure("Best Reward")
        plt.title("Best Reward per Generation")
        plt.xlabel("Generation")
        plt.ylabel("Reward")
        plt.plot(self.best_per_gen)
        plt.savefig(os.path.join(path, "best_reward.png"))

        # Plot mean reward of every generation with error bars
        plt.figure("Mean Reward")
        plt.title("Mean Reward per Generation")
        plt.xlabel("Generation")
        plt.ylabel("Reward")
        plt.plot(self.mean_per_gen)
        plt.errorbar(np.arange(len(self.mean_per_gen)), self.mean_per_gen, yerr=self.mean_error_per_gen, fmt='none', ecolor='r')
        plt.savefig(os.path.join(path, "mean_reward.png"))

        # Show plots
        if is_show:
            plt.show()