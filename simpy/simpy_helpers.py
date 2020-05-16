# Design philosophy: do not hide too much. Things that should be hidden are
# - collection of statistics
# These classes are abstract template classes. Fill in methods.

import simpy
import numpy as np

from collections import OrderedDict

class Debug:
    """
    Use this class to add debug statements to simulation output
    Doesn't necessarily need to be used outside of this file... but could be
    """
    DEBUG = False
    @staticmethod
    def info(msg):
        if Debug.DEBUG:
            print(msg)

class Stats:
    """
    Tracks both entities and resources so we can query for summary statistics at the end of the simulation.
    This is reset when Source.start() is called
    """
    summary = None
    def __init__(self):
        self.entities = []
        self.resources = {}
        Stats.summary = self
    
    # Entity Stats Methods
    
    @staticmethod
    def get_entities():
        Stats._check_for_instance_or_raise()
        return Stats.summary._get_disposed_entities()
    
    @staticmethod
    def get_total_times(attributes=None):
        Stats._check_for_instance_or_raise()
        filtered_entities = Stats.summary._filter_entities(attributes)
        return [entity.get_total_time() for entity in filtered_entities]

    @staticmethod
    def get_waiting_times(resource=None, attributes=None):
        Stats._check_for_instance_or_raise()
        
        if resource is not None:
            return Stats.summary._get_waiting_times_for_resource(resource, attributes)
        
        filtered_entities = Stats.summary._filter_entities(attributes)
        return [entity.get_total_waiting_time() for entity in filtered_entities]
    
    @staticmethod
    def get_processing_times(resource=None, attributes=None):
        Stats._check_for_instance_or_raise()
        
        if resource is not None:
            return Stats.summary._get_processing_times_for_resource(resource, attributes)
        
        filtered_entities = Stats.summary._filter_entities(attributes)
        return [entity.get_total_processing_time() for entity in filtered_entities]
    
    @staticmethod
    def queue_size_over_time(resource, sample_frequency=1):
        Stats._check_for_instance_or_raise()
        try:
            tracked_resource = Stats.summary.resources[resource.name]
            return tracked_resource.queue_size_over_time(sample_frequency)
        except KeyError:
            raise Exception(f"Resource {resource.name} was not visited during simulation")
    
    @staticmethod
    def utilization_over_time(resource, sample_frequency=1):
        Stats._check_for_instance_or_raise()
        try:
            tracked_resource = Stats.summary.resources[resource.name]
            return tracked_resource.utilization_over_time(sample_frequency)
        except KeyError:
            raise Exception(f"Resource {resource.name} was not visited during simulation")

    @staticmethod
    def number_being_processed_over_time(resource, sample_frequency=1):
        Stats._check_for_instance_or_raise()
        try:
            tracked_resource = Stats.summary.resources[resource.name]
            return tracked_resource.number_being_processed_over_time(sample_frequency)
        except KeyError:
            raise Exception(f"Resource {resource.name} was not visited during simulation")
    
    @staticmethod
    def _add_resource(resource):
        resource_name = resource.name
        if not resource_name in Stats.summary.resources:
            Stats.summary.resources[resource.name] = resource
    
    @staticmethod
    def _add_entity(entity):
        Stats.summary.entities.append(entity)
    
    @staticmethod
    def _check_for_instance_or_raise():
        if Stats.summary is None:
            raise Exception("Run a simulation before querying for statistics")
    
    @staticmethod
    def _filter_entities_on_matched_attributes(entities=[], attributes=None):
        if attributes is not None:
            return [entity for entity in entities if entity.matches_attributes(attributes)]
        return entities
    
    def _filter_entities(self, attributes):
        disposed_entities = Stats.summary._get_disposed_entities()
        return Stats._filter_entities_on_matched_attributes(disposed_entities, attributes)

    def _get_waiting_times_for_resource(self, resource, attributes):
        filtered_entities = self._filter_entities(attributes)
        return [entity.get_waiting_time_for_resource(resource) for entity in filtered_entities]
    
    def _get_processing_times_for_resource(self, resource, attributes):
        filtered_entities = self._filter_entities(attributes)
        return [entity.get_processing_time_for_resource(resource) for entity in filtered_entities]

    def _get_disposed_entities(self):
        return [entity for entity in Stats.summary.entities if entity.is_disposed()]
    

        
# This class defines methods to be mixed in to Resource and PriorityResource from simpy. 
class ResourceStatsMixin:
    VALID_SAMPLE_FREQUENCIES = [0.01, 0.1, 1]
    DECIMAL_MAP = { # maps sample frequencies to decimals
        .01: 2,
        .1: 1,
        1: 0
    }
    
    @staticmethod
    def _over_time(env, event_list, sample_frequency):
        if sample_frequency not in ResourceStatsMixin.VALID_SAMPLE_FREQUENCIES:
            raise NotImplementedError(f"You must pick a sample frequency in the list {ResourceStatsMixin.VALID_SAMPLE_FREQUENCIES}")

        decimals = ResourceStatsMixin.DECIMAL_MAP[sample_frequency] 
        rounded_event_list = ResourceStatsMixin._rounded_event_list(event_list, decimals)
        current_size = 0
        event_list_over_time = []
        for i in np.around(np.arange(0, env.now, sample_frequency), decimals):
            if i in rounded_event_list:
                # we found an activity that happened here
                last_queue_check = rounded_event_list[i][-1][0]
                current_size = last_queue_check
            event_list_over_time.append(current_size)
        
        return event_list_over_time
    
    @staticmethod
    def _rounded_event_list(event_list, decimals):
        """
        Necessary for turning the list of events collected that capture utilization and queue size over time
        into a "bucketed" list at rounded time intervals. 
        
        This allows queue/utilization sampling to work for continuous time.
        """
        rounded_event_list = {}
        for time, size, status in event_list:
            rounded_time = np.around(time, decimals)
            if rounded_time in rounded_event_list:
                rounded_event_list[rounded_time].append((size, status))
            else:
                rounded_event_list[rounded_time] = [(size, status)]
        return rounded_event_list
    
    def __init__(self, env, *args, **kwargs):
        super().__init__(env, *args, **kwargs)
        if self.service_time is None:
            raise NotImplementedError("You must define a function called 'service_time' in your Resource class")
        self.queue_size = []
        self.utilization_size = []
        self.env = env
        self.name = self.__class__.__name__

    def request(self, *args, **kwargs):
        req = super().request(*args, **kwargs)
        self.add_resource_check(event='request')
        return req

    def release(self, *args, **kwargs):
        rel = super().release(*args, **kwargs)
        self.utilization_size.append((self.env.now, self.count, 'release'))
        return rel
    
    def queue_size_over_time(self, sample_frequency=1):
        return ResourceStatsMixin._over_time(self.env, self.queue_size, sample_frequency)
    
    def number_being_processed_over_time(self, sample_frequency=1):
        return ResourceStatsMixin._over_time(self.env, self.utilization_size, sample_frequency)
    
    def utilization_over_time(self, sample_frequency=1):
        # iterate through each event, calculate the utilization
        utilization = [(x, np.around(y / float(self.capacity), decimals=2), e) for x, y, e in self.utilization_size]
        return ResourceStatsMixin._over_time(self.env, utilization, sample_frequency)    
    
    def add_resource_check(self, event='start'):
        self.utilization_size.append((self.env.now, self.count, event))
        self.queue_size.append((self.env.now, len(self.queue), event))
    

# all resources are priority resources
class Resource(ResourceStatsMixin, simpy.PriorityResource):
    pass

class Entity:
    # 0 has higher priority than 1. making 1 the default allows us to bump users to front of line
    DEFAULT_ENTITY_PRIORITY = 1
    @staticmethod
    def _empty_resource_tracking_dict():
        return { 'arrival_time': [], 'start_service_time': [], 'finish_service_time': [], 'request': None }

    def __init__(self, env, attributes = {}):
        """
        resources_requested - keeps track of all of the resources that were requested by this entity (in order of visitation)
        attributes - a list of keys/values that apply to this entity (gender, age, etc...)
        creation_time - when the entity was created (initialized in constructor)
        disposal_time - when the entity was disposed of
        """
        if self.process is None:
             raise NotImplementedError("You must define a function called 'process' in your entity class")
        
        self.attributes = attributes

        # Default priority for non-priority-entities is 0
        priority = Entity.DEFAULT_ENTITY_PRIORITY
        if "priority" in self.attributes:
            priority = self.attributes["priority"]
        elif "priority" in dir(self.__class__):
            priority = self.__class__.priority
        
        self.attributes["priority"] = priority
        self.env = env
        self.creation_time = None
        self.resources_requested = OrderedDict()
        self.disposal_time = None # remember to dispose of entities after finishing processing!
    
    def __str__(self):
        return f"{self.name} created_at: {self.creation_time} attributes: {self.attributes}"
    
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
        if self.is_disposed():
            self._calculate_statistics()
            return self.total_time
        else:
            raise Exception("Can't get total time: Entity has not been disposed")
    
    def get_total_waiting_time(self):
        """
        total time that the entity spent queued waiting for resources
        only accessible wonce the entity has been disposed
        """
        if self.is_disposed():
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
        if self.is_disposed():
            self._calculate_statistics()
            return self.processing_time
        else:
            raise Exception("Can't get total processing time: Entity has not been disposed")

    def get_processing_time_for_resource(self, resource):
        """
        time that the entity spent being processed by a particular resource
        """
        return self._calculate_processing_time_for_resource(resource.name)
    
    def wait_for_resource(self, resource, priority_override=None):
        """
        The time that a resource is requested
        should be logged as the "arrival time" for the resource.
        """
        Debug.info(f'{self.name} requesting {resource.name}: {self.env.now}')

        self._add_resource_to_visited(resource)
        self.resources_requested[resource.name]["arrival_time"].append(self.env.now)
        priority = priority_override if priority_override is not None else self.attributes["priority"]
        request = resource.request(priority=priority)
        self.resources_requested[resource.name]['request'] = request
        return request
    
    def process_at_resource(self, resource):
        Debug.info(f'{self.name} started processing at {resource.name} : {self.env.now}')        
        self.resources_requested[resource.name]["start_service_time"].append(self.env.now)
        resource.add_resource_check()
        try: 
            service_time = resource.service_time(self)
        except TypeError:
            # if students do not define a resource function that depends on entity
            # still allow them to call it.
            service_time = resource.service_time()
        except Exception:
            raise Exception(f"Error when calling {resource.name} service time function")
        return self.env.timeout(service_time)

    def release_resource(self, resource):
        request = self.resources_requested[resource.name]['request']
        if request is None:
            Debug.info(f"resource has already been released by {self.name}")
        else:
            Debug.info(f'{self.name} finished at {resource.name}: {self.env.now}')
            self.resources_requested[resource.name]["finish_service_time"].append(self.env.now)
            resource.release(request)
            self.resources_requested[resource.name]['request'] = None

    def dispose(self):
        """
        After an entity is finished being processed, it should be disposed
        """
        self.disposal_time = self.env.now
        Debug.info(f"{self.name} disposed: {self.disposal_time}")
        return self.disposal_time

    def is_disposed(self):
        return self.disposal_time is not None
    
    def did_visit_resource(self, resource_name):
        return resource_name in self.resources_requested

    def _calculate_waiting_time_for_resource(self, resource_name):
        if not self.did_visit_resource(resource_name):
            return None
        
        resource_stats = self.resources_requested[resource_name]
        return sum([start_time - arrival_time for start_time, arrival_time in zip(resource_stats["start_service_time"], resource_stats["arrival_time"])])

    def _calculate_processing_time_for_resource(self, resource_name):
        if not self.did_visit_resource(resource_name):
            return None
        
        resource_stats = self.resources_requested[resource_name]
        return sum([finish_time - start_time for finish_time, start_time in zip(resource_stats["finish_service_time"], resource_stats["start_service_time"])])

    def _calculate_statistics(self):
        if not self.is_disposed():
            raise Exception("Entity is not yet disposed. Dispose of this entity before calculating stats")
        waiting_time = 0
        processing_time = 0
        for resource_name, _ in self.resources_requested.items():
            waiting_time += self._calculate_waiting_time_for_resource(resource_name)
            processing_time += self._calculate_processing_time_for_resource(resource_name)

        self.total_time = self.disposal_time - self.creation_time
        self.waiting_time = waiting_time
        self.processing_time = processing_time

    def _add_resource_to_visited(self, resource):
        resource_name = resource.name
        Stats._add_resource(resource)
        if not resource_name in self.resources_requested:
            self.resources_requested[resource_name] = Entity._empty_resource_tracking_dict()
    
    def matches_attributes(self, attributes):
        for k, v in attributes.items():
            if k not in self.attributes or self.attributes[k] != v:
                return False
        return True
            
        


class Source:
    """
    keeps track of entities that have been produced for simluation
    """
    def __init__(self, env, first_creation=None, number=float("Inf")):
        if self.interarrival_time is None:
            raise NotImplementedError("Provide a method named interarrival_time_generator on your Source Class")
        self._interarrival_time_generator_template = self._interarrival_time_generator_factory() 
        self.env = env
        self.first_creation = first_creation
        self.number = number
        self.count = 0
    
    def next_entity(self):
        for time in self._interarrival_time_generator():
            self.count += 1
            if self.count > self.number:
                # we've reached the number we need to source
                # They will finish processing before simulation ends
                break 
            timeout = self.env.timeout(time)
            creation_time = self.env.now + time
            entity = self.build_entity()
            entity.creation_time = creation_time
            entity.name = f"{entity.__class__.__name__} {self.count}"
            entity.attributes["type"] = entity.__class__ # useful for filtering later
            Stats._add_entity(entity)
            yield timeout, entity        
    
    def start(self, debug=False):
        self._configure_debug(debug)
        self._initialize_stats()
        for arrival_time, entity in self.next_entity():
            yield arrival_time # wait for the next entity to appear
            Debug.info(entity)
            p = self.env.process(entity.process())
            p.callbacks.append(self._dispose(entity)) # disposal happens automatically
    
    # private methods
    
    def _initialize_stats(self):
        Stats()
    
    def _configure_debug(self, debug):
        Debug.DEBUG = debug
        if Debug.DEBUG:
            print("Debug is Enabled")
    
    def _interarrival_time_generator(self):
        # if first_creation exists, emit it as the first time, else just use the interarrival_time
        if self.first_creation is not None:
            yield self.first_creation
        for time in self._interarrival_time_generator_template:
            yield time
    
    def _interarrival_time_generator_factory(self):
        while True:
            yield self.interarrival_time()
    
    def _dispose(self, entity):
        """
        This is used to append dispose to the end of the entity.process callback list
        It needs to be a lambda. 
        """
        return lambda _: (entity.dispose())
    