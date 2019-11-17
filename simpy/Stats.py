# Entities should be able to store information about their trip through the system
# They should also be able to store attributes about themselves (gender, type, age) which could affect their treatment in the system.

# questions:
# How long did this entity spend in the system?
# How long did this entity spend at a particular resource (queue? in service? both combined?)

# primitives for each resource enter queue @ resource -> start processing @ resource -> exit resource
# if we have branches in resources, how do we know which resources an entity touched?
# -- e.g. if we have takeout and dine in as two separate resources.

import simpy
import numpy as np
from collections import OrderedDict

class Resource(simpy.Resource):
    def __init__(self, env, name='', service_time_generator=lambda:1, *args, **kwargs):
        super().__init__(env, *args, **kwargs)
        self.data = []
        self.service_time_generator = service_time_generator()
        self.env = env
        self.name = name

    def request(self, *args, **kwargs):
        self.data.append((self.env.now, len(self.queue)))
        return super().request(*args, **kwargs)


    def release(self, *args, **kwargs):
        self.data.append((self.env.now, len(self.queue)))
        return super().release(*args, **kwargs)

    # @abc.abstractmethod
    # def process_request(self, entity, request):
    #     pass

class Entity(object):

    @staticmethod
    def _empty_resource_tracking_dict():
        return { 'arrival_time': 0, 'start_service_time': 0, 'finish_service_time': 0 }

    def __init__(self, env, name, *args, **kwargs):
        """
        resources_requested - keeps track of all of the resources that were requested by this entity (in order of visitation)
        attributes - a list of keys/values that apply to this entity (gender, age, etc...)
        creation_time - when the entity was created (initialized in constructor)
        disposal_time - when the entity was disposed of
        """
        super().__init__(*args, **kwargs)
        self.env = env
        self.name = name
        self.creation_time = env.now
        self.resources_requested = OrderedDict()
        self.attributes = kwargs
        self.disposal_time = None # remember to dispose of entities after finishing processing!

    def set_attribute(self, attribute_name, attribute_value):
        """
        Record arbitrary set of attributes about the entity.
        Could include things like gender, age, anything really.
        Resources might use attributes to determine how a particular entity is processed.
        """
        self.attributes[attribute_name] = attribute_value

    def get_total_time(self):
        """
        total time that the entity spent in the system (from creation to disposal)
        only accessible once the entity has been disposed
        """
        if is_disposed():
            if not self.total_time:
                self._calculate_statistics()
            return self.total_time
        else:
            raise Exception("Can't get total time: Entity has not been disposed")

    def get_total_waiting_time(self):
        """
        total time that the entity spent queued waiting for resources
        only accessible wonce the entity has been disposed
        """
        if is_disposed():
            if not self.waiting_time:
                self._calculate_statistics()
            return self.waiting_time
        else:
            raise Exception("Can't get total waiting time: Entity has not been disposed")

    def get_waiting_time_for_resource(self, resource):
        """
        time that the entity spent waiting for a particular resource
        """
        return self._calculate_waiting_time_for_resource(resource.name)

    def get_total_processing_time(self):
        """
        total time that the entity spent being processed by resources
        """
        if is_disposed():
            if not self.processing_time:
                self._calculate_statistics()
            return self.processing_time
        else:
            raise Exception("Can't get total processing time: Entity has not been disposed")

    def get_processing_time_for_resource(self, resource):
        """
        time that the entity spent being processed by a particular resource
        """
        return self._calculate_processing_time_for_resource(resource.name)

    def request_resource(self, resource):
        """
        The time that a resource is requested
        should be logged as the "arrival time" for the resource.

        TODO: figure out how to uniquely identify resources if multiple are named the same.
        """
        self._add_resource_to_visited(resource.name)
        self.resources_requested[resource.name]["arrival_time"] = self.env.now
        return resource.request()

    def release_resource(self, resource, request):
        resource.release(request)

    def dispose(self):
        """
        After an entity is finished being processed, it should be disposed
        """
        self.disposal_time = self.env.now
        print(f"{self.name} disposed: {self.disposal_time}")
        return self.disposal_time

    def _is_disposed(self):
        return self.disposal_time is not None

    def _calculate_waiting_time_for_resource(self, resource_name):
        resource_stats = self.resources_requested[resource_name]
        return resource_stats["start_service_time"] - resource_stats["arrival_time"]

    def _calculate_processing_time_for_resource(self, resource_name):
        resource_stats = self.resources_requested[resource_name]
        return resource_stats["finish_service_time"] - resource_stats["start_service_time"]

    def _calculate_statistics(self):
        if not self._is_disposed():
            raise Exception("Entity is not yet disposed. Dispose of this entity before calculating stats")
        waiting_time = 0
        processing_time = 0

        for resource_name, _ in self.resources_requested.items():
            waiting_time += self._calculate_waiting_time_for_resource(resource_name)
            processing_time += self._calculate_processing_time_for_resource(resource_name)

        self.total_time = self.disposal_time - self.creation_time
        self.waiting_time = waiting_time
        self.processing_time = processing_time

    def _add_resource_to_visited(self, resource_name):
        self.resources_requested[resource_name] = Entity._empty_resource_tracking_dict()



def exponential_1():
    while True:
        yield np.random.exponential(scale=1.0)

# class Create(object):
#     """
#     Defines the arrival times for entities in the system
#     mechanisms for defining the arrival times

#     Things that would be nice to configure for creation
#     1) the interarrival times
#         - e.g. maybe you just want set interarrival times ()
#     """

#     def __init__(self, env, entity, *args, arrival_strategy=exponential_1, max_arrivals=np.inf, entities_per_arrival=1, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.entity = entity
#         self.env = env
#         self.arrival_strategy = arrival_strategy
#         self.max_arrivals = max_arrivals
#         self.entities_per_arrival = entities_per_arrival

#     def next_entity(self):
#         arrival = self.arrival_strategy()
#         yield self.env.timeout(arrival)
#         return self.entity(self.env)

class Source(object):
    """
    keeps track of entities that have been sourced
    """
    def __init__(self, entity):
        self.entity = entity
        self.entities = []

    def next_entity(self, *args, **kwargs):
        entity = self.entity(*args, **kwargs)
        self.entities.append(entity)
        return entity


class Dispose(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.disposed_entities = []

    def dispose(self, entity):

        """
        Disposes of the provided entity.
        This should be used on entities that have finished being processed.
        Returns the time that the entity was disposed.
        """
        self.disposed_entities.append(entity)
        entity.dispose()