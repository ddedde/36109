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
        self.queue_size = []
        self.service_time_generator = service_time_generator()
        self.env = env
        self.name = name

    def request(self, *args, **kwargs):
        req = super().request(*args, **kwargs)
        self.queue_size.append((self.env.now, len(self.queue), 'request'))
        return req

    def release(self, *args, **kwargs):
        rel = super().release(*args, **kwargs)
        self.queue_size.append((self.env.now, len(self.queue), 'release'))
        return rel
    
    def queue_size_over_time(self):
        return self.queue_size
        
    def process_entity(self, entity):
        raise NotImplementedError("Implement this method")

class Entity(object):

    @staticmethod
    def _empty_resource_tracking_dict():
        return { 'arrival_time': 0, 'start_service_time': 0, 'finish_service_time': 0 }

    def __init__(self, env, name, creation_time, *args, **kwargs):
        """
        resources_requested - keeps track of all of the resources that were requested by this entity (in order of visitation)
        attributes - a list of keys/values that apply to this entity (gender, age, etc...)
        creation_time - when the entity was created (initialized in constructor)
        disposal_time - when the entity was disposed of
        """
        super().__init__(*args, **kwargs)
        self.env = env
        self.name = name
        self.creation_time = creation_time
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
        if self._is_disposed():
            self._calculate_statistics()
            return self.total_time
        else:
            raise Exception("Can't get total time: Entity has not been disposed")

    def get_total_waiting_time(self):
        """
        total time that the entity spent queued waiting for resources
        only accessible wonce the entity has been disposed
        """
        if self._is_disposed():
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
        if self._is_disposed():
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
    
    def start_service_at_resource(self, resource):
        self.resources_requested[resource.name]["start_service_time"] = self.env.now

    def release_resource(self, resource, request):
        self.resources_requested[resource.name]["finish_service_time"] = self.env.now
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


class Source(object):
    """
    keeps track of entities that have been produced for simluation
    """
    def __init__(self, env, Entity, interarrival_time_generator):
        self.env = env
        self.Entity = Entity
        self.interarrival_time_generator = interarrival_time_generator
        self.entities = []

    def next_entity(self, *args, **kwargs):
        for time in self.interarrival_time_generator():
            timeout = self.env.timeout(time)
            creation_time = self.env.now + time
            entity = self.Entity(self.env, f"job_{creation_time}", creation_time, *args, **kwargs,)
            self.entities.append(entity)
            yield timeout, entity
    
    def get_entities(self):
        return self.entities
    
    def get_total_times(self):
        return [entity.get_total_time() for entity in self.entities]

    def get_waiting_times(self):
        return [entity.get_total_waiting_time() for entity in self.entities]
    
    def get_processing_times(self):
        return [entity.get_total_processing_time() for entity in self.entities]
    
    

        